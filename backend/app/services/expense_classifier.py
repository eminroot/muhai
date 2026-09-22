"""AI Expense Classification (Module 3).

Pure rule-based Turkish expense categoriser with a Gemini hook. The route layer
adds a per-vendor cache (learned from user corrections) consulted before this
falls back to keyword rules, and Gemini when configured.
"""
from __future__ import annotations

CATEGORIES = (
    "fuel",
    "restaurant",
    "office_supplies",
    "raw_materials",
    "marketing",
    "payroll",
    "rent",
    "utilities",
    "equipment",
    "software",
    "shipping",
    "travel",
    "bank_fees",
    "tax_payments",
    "maintenance",
    "insurance",
    "other",
)

# Keyword → category (Turkish + English). First match wins, order matters.
_RULES: list[tuple[str, tuple[str, ...]]] = [
    ("fuel", ("benzin", "mazot", "motorin", "akaryakıt", "petrol", "shell", "opet", "bp", "yakıt")),
    ("restaurant", ("restoran", "lokanta", "yemek", "kafe", "cafe", "kahve", "fast food", "starbucks")),
    ("rent", ("kira", "rent", "kiralama")),
    ("utilities", ("elektrik", "su faturası", "doğalgaz", "dogalgaz", "internet", "telefon", "telekom", "fatura")),
    ("payroll", ("maaş", "bordro", "ücret", "sgk", "personel")),
    ("tax_payments", ("vergi", "kdv", "muhtasar", "gib", "stopaj")),
    # Spend *intent* is checked before vendor brands: "Google reklam" is
    # marketing, not software, even though "google" is a software keyword (F12).
    ("marketing", ("reklam", "pazarlama", "marketing", "ilan", "sosyal medya", "ads")),
    ("software", ("yazılım", "software", "lisans", "abonelik", "saas", "microsoft", "google", "adobe", "hosting")),
    ("shipping", ("kargo", "nakliye", "gönderi", "shipping", "aras", "yurtiçi", "mng", "ptt")),
    ("travel", ("uçak", "otel", "konaklama", "bilet", "seyahat", "thy", "pegasus", "taksi")),
    ("bank_fees", ("banka", "komisyon", "havale", "eft", "masraf", "bsmv")),
    ("office_supplies", ("kırtasiye", "ofis", "kağıt", "toner", "kalem")),
    ("raw_materials", ("hammadde", "malzeme", "tedarik", "ham madde")),
    ("equipment", ("ekipman", "makine", "cihaz", "demirbaş", "bilgisayar", "donanım")),
    ("maintenance", ("bakım", "onarım", "tamir", "servis", "maintenance")),
    ("insurance", ("sigorta", "poliçe", "insurance", "dask", "kasko")),
]


# Turkish letters that OCR routinely strips to their ASCII base. Matching is
# done on the folded form of both sides so "bakim" still hits "bakım" (F9).
_FOLD = str.maketrans(
    {
        "ı": "i", "İ": "i", "ş": "s", "Ş": "s", "ğ": "g", "Ğ": "g",
        "ü": "u", "Ü": "u", "ö": "o", "Ö": "o", "ç": "c", "Ç": "c",
        "â": "a", "î": "i", "û": "u",
    }
)


def _fold(text: str) -> str:
    """Lowercase and strip Turkish diacritics for diacritic-insensitive matching."""
    return text.lower().translate(_FOLD)


# Pre-folded keyword table so folding happens once at import, not per call.
_FOLDED_RULES: list[tuple[str, tuple[str, ...]]] = [
    (category, tuple(_fold(k) for k in keywords)) for category, keywords in _RULES
]


def vendor_key(vendor: str | None) -> str:
    """Normalise a vendor name into the key learned categories are stored under.

    Folded, punctuation deleted and whitespace collapsed, so "Teknopark
    Gayrimenkul A.Ş." and "teknopark  gayrimenkul as" are the same vendor.

    Punctuation is *deleted* rather than turned into a space on purpose:
    Turkish company names end in "A.Ş.", "Ltd. Şti." and friends, and
    substituting spaces would make "A.Ş." ("a s") a different vendor from "AŞ"
    ("as"). The cost is that a hyphenated name no longer matches its spaced
    spelling, which is a real difference in a way an abbreviation's dots are not.

    The browser applies the identical transform in ``web/src/lib/db.js`` before
    it writes; if one side changes, both must.
    """
    if not vendor:
        return ""
    folded = _fold(vendor)
    cleaned = "".join(ch for ch in folded if ch.isalnum() or ch.isspace())
    return " ".join(cleaned.split())


def classify_expense(description: str | None, vendor: str | None = None) -> str:
    """Rule-based classification. Returns a category key (never raises)."""
    text = _fold(f"{vendor or ''} {description or ''}")
    for category, keywords in _FOLDED_RULES:
        if any(k in text for k in keywords):
            return category
    return "other"


def classify_with_ai(description: str, vendor: str, amount: float) -> str:
    """Gemini-backed classification, falling back to rules on any failure."""
    try:
        import google.generativeai as genai

        from app.core.config import settings

        if not settings.GEMINI_API_KEY:
            raise RuntimeError("no key")
        genai.configure(api_key=settings.GEMINI_API_KEY)
        model = genai.GenerativeModel("gemini-1.5-flash")
        prompt = (
            "Classify this Turkish business expense into one category. Return only "
            f"the category key from {list(CATEGORIES)}. "
            f"Expense: {description} from {vendor} for {amount} TL"
        )
        resp = model.generate_content(prompt)
        key = (getattr(resp, "text", "") or "").strip().lower()
        if key in CATEGORIES:
            return key
        raise ValueError("unexpected category")
    except Exception:
        return classify_expense(description, vendor)
