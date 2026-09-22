"""Offline assistant: BM25 retrieval, pre-answered questions, and composition.

The point of this backend is that it works with the network gone, so every
test here runs without touching Gemini or any other service.
"""
from __future__ import annotations

import pytest

from app.services import knowledge_base as kb
from app.services import tax_service as tax
from app.services.chat_service import (
    PRE_ANSWERS,
    BusinessContext,
    GeminiChatBackend,
    OfflineRagBackend,
)
from app.services.rag import Bm25Index, tokenize


@pytest.fixture()
def ctx() -> BusinessContext:
    return BusinessContext(
        monthly_revenue=480_000,
        monthly_expenses=395_000,
        cash_balance=210_000,
        unpaid_invoices=3,
        unpaid_amount=88_000,
        next_tax_type="KDV",
        next_tax_amount=41_000,
        next_tax_date="2026-09-26",
        low_stock_items=["Toner HP 26A"],
        muhai_score=72,
    )


@pytest.fixture()
def backend() -> OfflineRagBackend:
    return OfflineRagBackend()


# ── Tokenizer ──────────────────────────────────────────────────────────
def test_tokenizer_folds_turkish_diacritics():
    assert tokenize("kâr") == tokenize("kar")
    assert tokenize("gecikme zammı") == tokenize("gecikme zammi")


def test_tokenizer_stems_so_inflected_forms_collapse():
    # Turkish is agglutinative; these must land on the same key or retrieval
    # misses every question that does not use the bare nominative.
    assert tokenize("vergisi") == tokenize("vergiden") == tokenize("vergiyi")


def test_tokenizer_keeps_short_acronyms_intact():
    assert "kdv" in tokenize("KDV ne kadar")
    assert "sgk" in tokenize("SGK primi")


def test_tokenizer_drops_stopwords_and_single_chars():
    assert tokenize("ve ile bu a") == []


# ── BM25 ───────────────────────────────────────────────────────────────
def test_bm25_ranks_the_relevant_document_first():
    index = Bm25Index(
        [("a", "kedi köpek"), ("b", "amortisman demirbaş"), ("c", "fatura tahsilat")]
    )
    assert index.search("amortisman")[0].key == "b"


def test_bm25_returns_nothing_for_an_unrelated_query():
    index = Bm25Index([("a", "kedi köpek")])
    assert index.search("amortisman") == []


def test_bm25_handles_an_empty_query():
    assert Bm25Index([("a", "kedi")]).search("") == []


def test_ratio_is_bounded_coverage_not_raw_score():
    """`ratio` must stay in [0, 1] so one threshold means one thing."""
    index = Bm25Index([(d.id, d.indexed_text) for d in kb.DOCS])
    for query in ("amortisman", "kdv oranı", "amortisman demirbaş faydalı ömür"):
        for hit in index.search(query, k=5):
            assert 0.0 <= hit.ratio <= 1.0


def test_fully_understood_query_reaches_full_coverage():
    index = Bm25Index([(d.id, d.indexed_text) for d in kb.DOCS])
    assert index.search("amortisman")[0].ratio == pytest.approx(1.0)


def test_unknown_words_reduce_coverage():
    """Padding a query with words the corpus never saw must cost coverage.

    Ignoring them instead lets a mostly-nonsense question score 1.0 off one
    incidental hit, which is exactly how "Kedi besleyebilir miyim?" used to
    match the hiring entry.
    """
    index = Bm25Index([(d.id, d.indexed_text) for d in kb.DOCS])
    clean = index.search("amortisman")[0].ratio
    padded = index.search("amortisman zürafa teleskop lokomotif")[0].ratio
    assert padded < clean


# ── Pre-answered questions carry live figures ──────────────────────────
def test_vat_question_returns_the_live_amount(backend, ctx):
    reply = backend.reply("Bu ay ne kadar KDV ödeyeceğim?", ctx).reply
    assert "41.000 ₺" in reply
    assert "2026-09-26" in reply


def test_receivables_question_returns_live_counts(backend, ctx):
    reply = backend.reply("Kim bana borçlu?", ctx).reply
    assert "3" in reply and "88.000 ₺" in reply


def test_profit_question_shows_the_arithmetic(backend, ctx):
    reply = backend.reply("Bu ay kârım ne kadar?", ctx).reply
    assert "85.000 ₺" in reply  # 480.000 − 395.000
    assert "480.000 ₺" in reply and "395.000 ₺" in reply


def test_cash_question_reports_runway(backend, ctx):
    reply = backend.reply("Nakit durumum nasıl?", ctx).reply
    assert "210.000 ₺" in reply
    assert "0,5" in reply or "0.5" in reply  # 210k / 395k months


def test_profit_growth_question_is_actionable_and_grounded(backend, ctx):
    """The question that used to fall through to a canned reply."""
    reply = backend.reply("Ekstra kâr için ne yapmalıyım?", ctx).reply
    assert "85.000 ₺" in reply
    assert "88.000 ₺" in reply       # names the receivable to chase
    assert "Toner HP 26A" in reply   # names the stock-out risk


def test_low_stock_question_lists_the_products(backend, ctx):
    assert "Toner HP 26A" in backend.reply("stok durumu nasıl?", ctx).reply


def test_score_question_returns_the_score(backend, ctx):
    assert "72/100" in backend.reply("Muhai skorum kaç?", ctx).reply


# ── Knowledge-base retrieval supplies the domain explanation ───────────
@pytest.mark.parametrize(
    ("question", "expected_doc"),
    [
        ("Amortisman nedir?", "amortisman"),
        ("Gecikme zammı nasıl işler?", "gecikme-zammi"),
        ("e-Fatura zorunlu mu?", "e-fatura"),
        ("Damga vergisi oranı nedir?", "damga-vergisi"),
        ("Başabaş noktası nasıl bulunur?", "karlilik"),
    ],
)
def test_domain_questions_retrieve_the_right_passage(backend, ctx, question, expected_doc):
    reply = backend.reply(question, ctx).reply
    assert kb.DOCS_BY_ID[expected_doc].title in reply


def test_retrieved_answers_cite_their_source(backend, ctx):
    assert "Kaynak:" in backend.reply("Amortisman nedir?", ctx).reply


def test_retrieval_survives_missing_diacritics(backend, ctx):
    """OCR and phone keyboards both drop Turkish diacritics."""
    with_marks = backend.reply("Gecikme zammı nasıl işler?", ctx).reply
    without = backend.reply("Gecikme zammi nasil isler?", ctx).reply
    assert without == with_marks


def test_answer_composes_live_figures_with_domain_knowledge(backend, ctx):
    """A VAT question should get both the amount and how VAT works."""
    reply = backend.reply("Bu ay ne kadar KDV ödeyeceğim?", ctx).reply
    assert "41.000 ₺" in reply                       # the live figure
    assert "indirilecek KDV" in reply or "net" in reply  # the explanation


# ── Behaviour at the edges ─────────────────────────────────────────────
def test_source_is_always_offline(backend, ctx):
    for q in ("KDV ne kadar?", "Amortisman nedir?", "asdfgh"):
        assert backend.reply(q, ctx).source == "offline"


def test_unknown_question_gets_a_helpful_default(backend, ctx):
    reply = backend.reply("Bugün hava nasıl olacak?", ctx)
    assert reply.source == "offline"
    assert "KDV" in reply.reply  # steers the user to what it can answer


def test_empty_context_does_not_crash(backend):
    """A brand-new company has zeros everywhere — no division by zero."""
    empty = BusinessContext()
    for q in ("Nakit durumum nasıl?", "Ekstra kâr için ne yapmalıyım?", "stok durumu"):
        assert backend.reply(q, empty).reply


def test_every_pre_answer_renders_for_an_empty_context():
    empty = BusinessContext()
    for entry in PRE_ANSWERS:
        assert entry.answer(empty), f"{entry.id} produced no text"


# ── Gemini degrades to offline rather than to nothing ──────────────────
def test_gemini_failure_falls_back_to_retrieval(monkeypatch, ctx):
    backend = GeminiChatBackend()
    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda *a, **k: (_ for _ in ()).throw(OSError("network down")),
    )
    reply = backend.reply("Amortisman nedir?", ctx)
    assert reply.source == "offline"
    assert kb.DOCS_BY_ID["amortisman"].title in reply.reply


# ── The knowledge base must not drift from the tax engine ──────────────
def test_knowledge_base_quotes_the_engines_own_rates():
    vat = kb.DOCS_BY_ID["kdv-oranlari"].text
    assert f"%{tax.VAT_STANDARD * 100:.0f}" in vat

    sgk = kb.DOCS_BY_ID["sgk-primleri"].text
    assert "%14" in sgk                 # SGK_EMPLOYEE_RATE
    assert "%19,5" in sgk               # SGK_EMPLOYER_RATE


def test_every_document_is_indexable():
    for doc in kb.DOCS:
        assert tokenize(doc.indexed_text), f"{doc.id} tokenises to nothing"


def test_document_ids_are_unique():
    ids = [d.id for d in kb.DOCS]
    assert len(ids) == len(set(ids))
