"""Turkish invoice post-processing layer (Module 1 — Document Intelligence).

Pure, side-effect-free functions that turn raw OCR text into rich structured
fields: company identity (VKN/TCKN/MERSIS/vergi dairesi), invoice metadata
(number, dates, currency, payment method), and tax details (KDV rate/amount,
stopaj, tevkifat, exemptions). Also auto-detects the invoice type
(e-Fatura / e-Arşiv / paper) and recognised Turkish tax phrases.

No Tesseract / Pillow dependency here, so the whole layer is trivially
unit-testable against text fixtures.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

InvoiceType = Literal["e_fatura", "e_arsiv", "paper"]

# ── Identity ───────────────────────────────────────────────────────────
# VKN (corporate tax no) = 10 digits; TCKN (national id) = 11 digits.
_VKN_LABELLED_RE = re.compile(
    r"(?:vkn|vergi\s*(?:kimlik\s*)?(?:no|numaras[ıi]))\s*[:#]?\s*(\d{10})\b",
    re.IGNORECASE,
)
_TCKN_LABELLED_RE = re.compile(
    r"(?:tckn|t\.?\s*c\.?\s*(?:kimlik)?\s*(?:no|numaras[ıi]))\s*[:#]?\s*(\d{11})\b",
    re.IGNORECASE,
)
_VKN_BARE_RE = re.compile(r"\b(\d{10})\b")
_TCKN_BARE_RE = re.compile(r"\b(\d{11})\b")
_MERSIS_RE = re.compile(
    r"(?:mersis)\s*(?:no)?\s*[:#]?\s*(\d{16})\b", re.IGNORECASE
)
_TAX_OFFICE_RE = re.compile(
    r"vergi\s*dairesi\s*[:#]?\s*([A-Za-zÇĞİÖŞÜçğıöşü\.\s]{2,40})", re.IGNORECASE
)

# ── Invoice metadata ───────────────────────────────────────────────────
_DUE_DATE_RE = re.compile(
    r"(?:vade(?:\s*tarihi)?|son\s*[öo]deme(?:\s*tarihi)?)\s*[:#]?\s*"
    r"(\d{1,2})[./-](\d{1,2})[./-](\d{2,4})",
    re.IGNORECASE,
)
_PAYMENT_METHODS: list[tuple[str, str]] = [
    ("nakit", "Nakit"),
    ("kredi\\s*kart", "Kredi Kartı"),
    ("havale", "Havale"),
    ("eft", "EFT"),
    ("çek|cek", "Çek"),
    ("banka\\s*kart", "Banka Kartı"),
]
_CURRENCIES: list[tuple[str, str]] = [
    (r"\bUSD\b|\$|amerikan\s*dolar", "USD"),
    (r"\bEUR\b|€|euro", "EUR"),
    (r"\bGBP\b|£|sterlin", "GBP"),
    (r"\bTRY\b|\bTL\b|₺|türk\s*liras", "TRY"),
]

# ── Tax ────────────────────────────────────────────────────────────────
_KDV_RATE_RE = re.compile(r"(?:kdv|vat)[^%\d]{0,12}%\s*(\d{1,2})", re.IGNORECASE)
_RATE_ONLY_RE = re.compile(r"%\s*(\d{1,2})\b")
_STOPAJ_RE = re.compile(r"(?:stopaj|g[.\s]*v[.\s]*stopaj)", re.IGNORECASE)
_AMOUNT_RE = re.compile(r"(\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{2}))")
_VALID_KDV_RATES = {1, 8, 10, 18, 20}  # 8/18 historical, kept for older docs


def parse_amount(raw: str) -> float | None:
    """Parse a Turkish-formatted number like '1.234,56' -> 1234.56."""
    s = raw.strip()
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".")
    elif "," in s:
        s = s.replace(",", ".")
    try:
        return round(float(s), 2)
    except ValueError:
        return None


def _amounts_on_line(line: str) -> list[float]:
    return [a for a in (parse_amount(m) for m in _AMOUNT_RE.findall(line)) if a is not None]


@dataclass
class ParsedInvoice:
    invoice_type: InvoiceType = "paper"
    vkn: str | None = None
    tckn: str | None = None
    mersis: str | None = None
    tax_office: str | None = None
    currency: str = "TRY"
    payment_method: str | None = None
    due_date: str | None = None  # ISO yyyy-mm-dd
    kdv_rate: int | None = None  # percent, e.g. 20
    kdv_amount: float | None = None
    net_amount: float | None = None
    total_amount: float | None = None
    stopaj_amount: float | None = None
    is_kdv_inclusive: bool | None = None
    tevkifat: bool = False
    istisna: bool = False
    ihrac_kayitli: bool = False
    detected_phrases: list[str] = field(default_factory=list)


def detect_invoice_type(text: str) -> InvoiceType:
    """e-Arşiv and e-Fatura beat plain paper; checked in priority order."""
    low = text.lower()
    if "arşiv" in low or "arsiv" in low or "e-arşiv" in low:
        return "e_arsiv"
    if (
        "e-fatura" in low
        or "e fatura" in low
        or "efatura" in low
        or "ettn" in low  # e-fatura unique reference
    ):
        return "e_fatura"
    return "paper"


def _first_group(regex: re.Pattern[str], text: str) -> str | None:
    m = regex.search(text)
    return m.group(1).strip() if m else None


def _detect_currency(text: str) -> str:
    for pattern, code in _CURRENCIES:
        if re.search(pattern, text, re.IGNORECASE):
            return code
    return "TRY"


def _detect_payment_method(text: str) -> str | None:
    for pattern, label in _PAYMENT_METHODS:
        if re.search(pattern, text, re.IGNORECASE):
            return label
    return None


def _detect_due_date(text: str) -> str | None:
    m = _DUE_DATE_RE.search(text)
    if not m:
        return None
    d, mo, y = m.groups()
    if len(y) == 2:
        y = "20" + y
    try:
        return datetime(int(y), int(mo), int(d)).date().isoformat()
    except ValueError:
        return None


def _detect_kdv_rate(text: str) -> int | None:
    m = _KDV_RATE_RE.search(text)
    if m:
        rate = int(m.group(1))
        if rate in _VALID_KDV_RATES:
            return rate
    # Fall back to any standalone percentage that is a valid KDV rate.
    for raw in _RATE_ONLY_RE.findall(text):
        rate = int(raw)
        if rate in _VALID_KDV_RATES:
            return rate
    return None


def _detect_identity(parsed: ParsedInvoice, text: str) -> None:
    parsed.vkn = _first_group(_VKN_LABELLED_RE, text)
    parsed.tckn = _first_group(_TCKN_LABELLED_RE, text)
    parsed.mersis = _first_group(_MERSIS_RE, text)
    office = _first_group(_TAX_OFFICE_RE, text)
    if office:
        # Trim trailing label noise; keep the first line's worth.
        parsed.tax_office = office.splitlines()[0].strip(" .:-")

    # Bare fallbacks (only when not already labelled), avoiding MERSIS digits.
    if parsed.tckn is None:
        for cand in _TCKN_BARE_RE.findall(text):
            if parsed.mersis and cand in parsed.mersis:
                continue
            parsed.tckn = cand
            break
    if parsed.vkn is None and parsed.tckn is None:
        for cand in _VKN_BARE_RE.findall(text):
            if parsed.mersis and cand in parsed.mersis:
                continue
            parsed.vkn = cand
            break


def _detect_phrases(parsed: ParsedInvoice, text: str) -> None:
    low = text.lower()
    phrase_map = [
        ("kdv dahil", "KDV Dahil"),
        ("kdv hariç", "KDV Hariç"),
        ("kdv haric", "KDV Hariç"),
        ("tevkifat", "Tevkifatlı"),
        ("istisna", "İstisna"),
        ("i̇stisna", "İstisna"),
        ("ihraç kayıtlı", "İhraç Kayıtlı"),
        ("ihrac kayitli", "İhraç Kayıtlı"),
    ]
    seen: list[str] = []
    for needle, label in phrase_map:
        if needle in low and label not in seen:
            seen.append(label)
    parsed.detected_phrases = seen

    if "kdv dahil" in low:
        parsed.is_kdv_inclusive = True
    elif "kdv hariç" in low or "kdv haric" in low:
        parsed.is_kdv_inclusive = False
    parsed.tevkifat = "tevkifat" in low
    parsed.istisna = "istisna" in low or "i̇stisna" in low
    parsed.ihrac_kayitli = "ihraç kayıtlı" in low or "ihrac kayitli" in low


def _detect_amounts(parsed: ParsedInvoice, text: str) -> None:
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    kdv_candidates: list[float] = []
    total_candidates: list[float] = []
    net_candidates: list[float] = []
    stopaj_candidates: list[float] = []

    for ln in lines:
        low = ln.lower()
        amounts = _amounts_on_line(ln)
        if not amounts:
            continue
        if "kdv" in low or "vat" in low:
            kdv_candidates.extend(amounts)
        if _STOPAJ_RE.search(ln):
            stopaj_candidates.extend(amounts)
        if any(k in low for k in ("genel toplam", "toplam", "total", "tutar")):
            total_candidates.extend(amounts)
        if any(k in low for k in ("mal hizmet", "ara toplam", "matrah", "net")):
            net_candidates.extend(amounts)

    all_amounts = [a for ln in lines for a in _amounts_on_line(ln)]
    if kdv_candidates:
        parsed.kdv_amount = max(kdv_candidates)
    if stopaj_candidates:
        parsed.stopaj_amount = max(stopaj_candidates)
    parsed.total_amount = (
        max(total_candidates) if total_candidates else (max(all_amounts) if all_amounts else None)
    )
    if net_candidates:
        parsed.net_amount = max(net_candidates)

    # Derive whichever of net/kdv is missing when we have enough signal.
    if parsed.total_amount is not None:
        if parsed.net_amount is None and parsed.kdv_amount is not None:
            parsed.net_amount = round(parsed.total_amount - parsed.kdv_amount, 2)
        elif (
            parsed.net_amount is None
            and parsed.kdv_rate is not None
            and parsed.is_kdv_inclusive
        ):
            net = parsed.total_amount / (1 + parsed.kdv_rate / 100)
            parsed.net_amount = round(net, 2)
            if parsed.kdv_amount is None:
                parsed.kdv_amount = round(parsed.total_amount - net, 2)


def parse_invoice_text(text: str) -> ParsedInvoice:
    """Full structured extraction from raw OCR text."""
    parsed = ParsedInvoice(invoice_type=detect_invoice_type(text))
    _detect_identity(parsed, text)
    parsed.currency = _detect_currency(text)
    parsed.payment_method = _detect_payment_method(text)
    parsed.due_date = _detect_due_date(text)
    parsed.kdv_rate = _detect_kdv_rate(text)
    _detect_phrases(parsed, text)
    _detect_amounts(parsed, text)
    return parsed
