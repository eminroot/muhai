"""AI Business Advisor chatbot service (Module 9).

A Turkish-language CFO assistant. When a Gemini API key is configured it answers
with the live business context injected into the prompt; otherwise it falls back
to a deterministic keyword matcher (also context-aware) so the app works fully
offline and in tests.

The ``ChatBackend`` interface keeps the API contract stable across backends.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import asdict, dataclass

from app.schemas.chat import ChatResponse
from app.services import knowledge_base as kb
from app.services.rag import Bm25Index

SYSTEM_PROMPT = (
    "Sen Muhai'sin. Türk KOBİ'ler için yapay zeka destekli bir CFO asistanısın. "
    "Kullanıcının işletme verilerine erişimin var. Sorulara kısa, net, Türkçe "
    "cevaplar ver. Finansal tavsiyeler için her zaman hesaplamaları göster."
)

# Quick-question chips shown in the UI.
QUICK_QUESTIONS: list[str] = [
    "Bu ay ne kadar KDV ödeyeceğim?",
    "Bu ay SGK ne kadar?",
    "Kim bana borçlu?",
    "Bu çeyrekte kâr ne kadar?",
    "Yeni çalışan alabilir miyim?",
    "Hangi giderler en yüksek?",
]


@dataclass
class BusinessContext:
    monthly_revenue: float = 0.0
    monthly_expenses: float = 0.0
    cash_balance: float = 0.0
    unpaid_invoices: int = 0
    unpaid_amount: float = 0.0
    next_tax_type: str | None = None
    next_tax_amount: float = 0.0
    next_tax_date: str | None = None
    low_stock_items: list[str] | None = None
    muhai_score: int = 0

    def as_prompt_block(self) -> str:
        import json

        data = asdict(self)
        data["low_stock_items"] = self.low_stock_items or []
        return json.dumps(data, ensure_ascii=False)


# ── Offline answering: pre-answered questions + RAG ────────────────────
# The offline path is not a degraded mode bolted on for tests — a dead venue
# network must still produce a real answer. It has two halves:
#
#   1. Pre-answered questions, which carry the *live* figures out of
#      BusinessContext. These are what a user actually asks day to day, and
#      only the app knows the numbers, so no corpus can supply them.
#   2. Retrieval over knowledge_base.DOCS, which supplies the domain
#      explanation — rates, rules, method — that the numbers alone do not give.
#
# A good answer usually wants both: "your VAT is ~41.000 ₺" plus "here is how
# VAT is computed and when it is due". So they are composed, not chosen
# between.


@dataclass(frozen=True)
class PreAnswer:
    """A question we can answer from BusinessContext without any model."""

    id: str
    # Several phrasings, indexed together — users do not type the canonical one.
    questions: tuple[str, ...]
    answer: Callable[[BusinessContext], str]

    @property
    def indexed_text(self) -> str:
        return " ".join(self.questions)


def _profit(ctx: BusinessContext) -> float:
    return ctx.monthly_revenue - ctx.monthly_expenses


def _tl(value: float) -> str:
    """1234567.0 -> '1.234.567 ₺' (Turkish digit grouping)."""
    return f"{value:,.0f}".replace(",", ".") + " ₺"


def _a_kdv(ctx: BusinessContext) -> str:
    if ctx.next_tax_type == "KDV" and ctx.next_tax_amount:
        due = f" Son ödeme tarihi {ctx.next_tax_date}." if ctx.next_tax_date else ""
        return f"Bu dönem tahmini KDV yükünüz {_tl(ctx.next_tax_amount)}.{due}"
    return (
        "Bu dönem için hesaplanmış bir KDV tutarı görünmüyor. Ödenecek KDV, "
        "satış KDV'nizden alış KDV'nizi düşerek bulunur."
    )


def _a_sgk(ctx: BusinessContext) -> str:
    if ctx.next_tax_type and "SGK" in ctx.next_tax_type.upper():
        due = f" Son ödeme tarihi {ctx.next_tax_date}." if ctx.next_tax_date else ""
        return f"Yaklaşan SGK yükümlülüğünüz {_tl(ctx.next_tax_amount)}.{due}"
    return (
        "Yaklaşan yükümlülükleriniz arasında SGK görünmüyor. Bordro sayfasından "
        "çalışan bazında prim dökümünü görebilirsiniz."
    )


def _a_receivables(ctx: BusinessContext) -> str:
    if not ctx.unpaid_invoices:
        return "Şu an vadesi geçmiş alacağınız görünmüyor."
    return (
        f"{ctx.unpaid_invoices} ödenmemiş faturanız var; toplam "
        f"{_tl(ctx.unpaid_amount)} alacağınız bulunuyor."
    )


def _a_profit(ctx: BusinessContext) -> str:
    return (
        f"Bu ay tahmini kârınız {_tl(_profit(ctx))} "
        f"(gelir {_tl(ctx.monthly_revenue)} − gider {_tl(ctx.monthly_expenses)})."
    )


def _a_cash(ctx: BusinessContext) -> str:
    months = (
        ctx.cash_balance / ctx.monthly_expenses if ctx.monthly_expenses > 0 else None
    )
    tail = (
        f" Bu, mevcut gider hızınızla yaklaşık {months:.1f} aylık rezerve denk geliyor."
        if months is not None
        else ""
    )
    return f"Nakit bakiyeniz {_tl(ctx.cash_balance)}.{tail}"


def _a_hiring(ctx: BusinessContext) -> str:
    return (
        f"Nakdiniz {_tl(ctx.cash_balance)}, aylık kârınız {_tl(_profit(ctx))}. "
        "İşe alım kararını bu ikisine göre verin: çalışanın toplam maliyeti brüt "
        "maaşın üzerine işveren primleri eklenerek bulunur."
    )


def _a_expenses(ctx: BusinessContext) -> str:
    return (
        f"Bu ay toplam gideriniz {_tl(ctx.monthly_expenses)}. Kalem kalem dağılımı "
        "Nakit Akışı sekmesindeki kategori grafiğinden görebilirsiniz."
    )


def _a_stock(ctx: BusinessContext) -> str:
    if ctx.low_stock_items:
        return "Kritik seviyedeki ürünler: " + ", ".join(ctx.low_stock_items) + "."
    return "Şu an kritik stok seviyesinin altında ürününüz yok."


def _a_score(ctx: BusinessContext) -> str:
    return (
        f"Muhai Skorunuz {ctx.muhai_score}/100. Kategori kırılımını panelden "
        "inceleyebilirsiniz."
    )


def _a_more_profit(ctx: BusinessContext) -> str:
    lines = [f"Mevcut aylık kârınız {_tl(_profit(ctx))}. Verinize göre öncelik sırası:"]
    if ctx.unpaid_amount > 0:
        lines.append(
            f"1) {_tl(ctx.unpaid_amount)} tutarındaki {ctx.unpaid_invoices} ödenmemiş "
            "faturayı tahsil edin — bu nakit yeni satış gerektirmiyor."
        )
    if ctx.monthly_expenses > 0:
        lines.append(
            f"2) {_tl(ctx.monthly_expenses)} tutarındaki aylık giderinizin en büyük "
            "kalemlerini tek tek gözden geçirin."
        )
    if ctx.low_stock_items:
        lines.append(
            "3) Kritik stoktaki ürünleri ("
            + ", ".join(ctx.low_stock_items)
            + ") tamamlayın; stok tükenmesi doğrudan satış kaybıdır."
        )
    return "\n".join(lines)


PRE_ANSWERS: tuple[PreAnswer, ...] = (
    PreAnswer(
        "kdv",
        ("bu ay ne kadar kdv ödeyeceğim", "kdv borcum ne kadar", "kdv tutarı",
         "ne kadar kdv var", "katma değer vergisi ne kadar"),
        _a_kdv,
    ),
    PreAnswer(
        "sgk",
        ("bu ay sgk ne kadar", "sgk primi ne kadar", "sgk borcum",
         "sigorta primi tutarı"),
        _a_sgk,
    ),
    PreAnswer(
        "alacak",
        ("kim bana borçlu", "alacaklarım ne kadar", "tahsil edemediğim faturalar",
         "ödenmemiş fatura", "vadesi geçmiş alacak"),
        _a_receivables,
    ),
    PreAnswer(
        "kar",
        ("bu çeyrekte kâr ne kadar", "kârım ne kadar", "ne kadar kazandım",
         "bu ay kâr durumu"),
        _a_profit,
    ),
    PreAnswer(
        "nakit",
        ("nakit durumum nasıl", "kasamda ne kadar var", "nakit bakiyem",
         "param ne kadar", "likidite durumu"),
        _a_cash,
    ),
    PreAnswer(
        "ise-alim",
        ("yeni çalışan alabilir miyim", "işe alım yapabilir miyim",
         "eleman alsam olur mu", "personel alımı"),
        _a_hiring,
    ),
    PreAnswer(
        "gider",
        ("hangi giderler en yüksek", "giderlerim ne kadar", "masraflarım",
         "en çok nereye harcıyorum"),
        _a_expenses,
    ),
    PreAnswer(
        "stok",
        ("stok durumu nasıl", "hangi ürünler azaldı", "kritik stok",
         "envanter durumu"),
        _a_stock,
    ),
    PreAnswer(
        "skor",
        ("muhai skorum kaç", "finansal sağlığım nasıl", "skorum ne durumda"),
        _a_score,
    ),
    PreAnswer(
        "kar-artirma",
        ("ekstra kâr için ne yapmalıyım", "kârımı nasıl artırırım",
         "daha çok kazanmak için ne yapmalıyım", "gelirimi nasıl büyütürüm",
         "işimi nasıl büyütürüm", "ne yapmalıyım"),
        _a_more_profit,
    ),
)

_PRE_BY_ID = {p.id: p for p in PRE_ANSWERS}
_PRE_INDEX = Bm25Index([(p.id, p.indexed_text) for p in PRE_ANSWERS])
_KB_INDEX = Bm25Index([(d.id, d.indexed_text) for d in kb.DOCS])

# Retrieval acceptance thresholds, expressed as a fraction of the best score
# the query could possibly reach (Hit.ratio), so they mean the same thing for
# a two-word and a ten-word question. The pre-answer bar is higher because a
# wrong live figure is worse than a missing one; the knowledge-base bar is
# lower because an approximately-relevant explanation still helps.
# Measured against the real corpus: genuine pre-answer matches score 1.00 while
# the nearest false positives ("Kedi besleyebilir miyim?" catching the hiring
# entry on "miyim") top out at 0.39, so 0.55 sits in open space between them.
# The knowledge-base bar is far lower because queries with no real overlap
# score 0 there and never reach it — the risk is a missed explanation, not a
# wrong one.
_PRE_MIN_RATIO = 0.55
_KB_MIN_RATIO = 0.20

_DEFAULT_REPLY = (
    "Bunu çevrimdışı olarak yanıtlayamadım. KDV, SGK, kâr, nakit, gider, "
    "tahsilat, stok, işe alım veya Muhai Skoru hakkında soru sorabilirsiniz."
)


class ChatBackend(ABC):
    @abstractmethod
    def reply(self, message: str, ctx: BusinessContext) -> ChatResponse:  # pragma: no cover
        ...


class OfflineRagBackend(ChatBackend):
    """Answers with no network: live figures plus retrieved domain knowledge."""

    def reply(self, message: str, ctx: BusinessContext) -> ChatResponse:
        parts: list[str] = []
        sources: list[str] = []

        pre_hits = _PRE_INDEX.search(message, k=1)
        if pre_hits and pre_hits[0].ratio >= _PRE_MIN_RATIO:
            parts.append(_PRE_BY_ID[pre_hits[0].key].answer(ctx))

        kb_hits = _KB_INDEX.search(message, k=1)
        if kb_hits and kb_hits[0].ratio >= _KB_MIN_RATIO:
            doc = kb.DOCS_BY_ID[kb_hits[0].key]
            parts.append(doc.text)
            sources.append(doc.title)

        if not parts:
            return ChatResponse(reply=_DEFAULT_REPLY, source="offline")

        reply = "\n\n".join(parts)
        if sources:
            reply += "\n\nKaynak: " + ", ".join(sources)
        return ChatResponse(reply=reply, source="offline")

# Stable, generally-available Flash model. Overridable via GEMINI_MODEL so the
# model can be changed without touching code. The previously hardcoded
# "gemini-1.5-flash" has been retired and 404s on the v1beta endpoint.
GEMINI_MODEL_DEFAULT = "gemini-2.5-flash"
_GEMINI_ENDPOINT = (
    "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
)
_GEMINI_TIMEOUT = 20


class GeminiChatBackend(ChatBackend):
    """Calls Gemini with the system prompt + business context injected.

    Talks to the REST endpoint with the standard library rather than the
    google-generativeai SDK: that package was never in requirements.txt, so the
    old ``import google.generativeai`` raised ImportError on every call and this
    backend silently degraded to the rule matcher. Stdlib only — no new
    dependency, no image rebuild.

    Falls back to OfflineRagBackend on any error (network, quota, bad key),
    so a network failure degrades to real retrieval rather than to nothing.
    """

    def __init__(self) -> None:
        self._fallback = OfflineRagBackend()

    def reply(self, message: str, ctx: BusinessContext) -> ChatResponse:
        try:
            import json
            import urllib.request

            from app.core.config import settings

            model = getattr(settings, "GEMINI_MODEL", "") or GEMINI_MODEL_DEFAULT
            instruction = f"{SYSTEM_PROMPT}\nMevcut veriler: {ctx.as_prompt_block()}"
            payload = {
                "system_instruction": {"parts": [{"text": instruction}]},
                "contents": [{"role": "user", "parts": [{"text": message}]}],
            }
            req = urllib.request.Request(
                _GEMINI_ENDPOINT.format(model=model),
                data=json.dumps(payload).encode("utf-8"),
                headers={
                    "Content-Type": "application/json",
                    # Key travels in a header, not the query string, so it does
                    # not end up in proxy or access logs.
                    "x-goog-api-key": settings.GEMINI_API_KEY,
                },
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=_GEMINI_TIMEOUT) as resp:
                body = json.load(resp)

            parts = body["candidates"][0]["content"]["parts"]
            text = "".join(p.get("text", "") for p in parts).strip()
            if not text:
                raise ValueError("empty response")
            return ChatResponse(reply=text, source="ai")
        except Exception:
            return self._fallback.reply(message, ctx)


def _select_backend() -> ChatBackend:
    try:
        from app.core.config import settings

        if getattr(settings, "GEMINI_API_KEY", ""):
            return GeminiChatBackend()
    except Exception:
        pass
    return OfflineRagBackend()


_backend: ChatBackend = _select_backend()


def get_chat_reply(message: str, ctx: BusinessContext | None = None) -> ChatResponse:
    return _backend.reply(message, ctx or BusinessContext())
