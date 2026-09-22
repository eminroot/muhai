"""Turkish invoice text parsing — pure, runs against text fixtures only."""
from app.services.ocr_parser import (
    detect_invoice_type,
    parse_amount,
    parse_invoice_text,
)

EFATURA_FIXTURE = """
ATLAS TICARET LTD. STI.
e-Fatura
Vergi Dairesi: Kadikoy
VKN: 1234567890
MERSIS No: 0123456789012345
Fatura No: ATL2026000001
Vade Tarihi: 15.07.2026
Odeme Sekli: Havale

Mal Hizmet Toplam    1.000,00 TL
KDV %20                200,00 TL
Genel Toplam         1.200,00 TL
"""


# ── Number parsing ─────────────────────────────────────────────────────
def test_parse_amount_turkish_thousands_and_decimal():
    assert parse_amount("1.234,56") == 1234.56


def test_parse_amount_decimal_comma_only():
    assert parse_amount("1234,56") == 1234.56


def test_parse_amount_plain_decimal_point():
    assert parse_amount("1234.56") == 1234.56


def test_parse_amount_returns_none_for_garbage():
    assert parse_amount("abc") is None


# ── Invoice type ───────────────────────────────────────────────────────
def test_detect_efatura():
    assert detect_invoice_type("Bu bir e-Fatura belgesidir") == "e_fatura"


def test_detect_earsiv_takes_priority():
    assert detect_invoice_type("e-Arsiv Fatura") == "e_arsiv"


def test_detect_paper_default():
    assert detect_invoice_type("Sadece duz bir fatura metni") == "paper"


def test_detect_efatura_via_ettn():
    assert detect_invoice_type("ETTN: abc-123") == "e_fatura"


# ── Full extraction ────────────────────────────────────────────────────
def test_parses_identity_fields():
    p = parse_invoice_text(EFATURA_FIXTURE)
    assert p.vkn == "1234567890"
    assert p.mersis == "0123456789012345"
    assert p.tax_office is not None and "Kadikoy" in p.tax_office


def test_parses_invoice_type_and_currency():
    p = parse_invoice_text(EFATURA_FIXTURE)
    assert p.invoice_type == "e_fatura"
    assert p.currency == "TRY"


def test_parses_kdv_rate():
    assert parse_invoice_text(EFATURA_FIXTURE).kdv_rate == 20


def test_parses_due_date_to_iso():
    assert parse_invoice_text(EFATURA_FIXTURE).due_date == "2026-07-15"


def test_parses_payment_method():
    assert parse_invoice_text(EFATURA_FIXTURE).payment_method == "Havale"


def test_detects_tevkifat_phrase():
    p = parse_invoice_text("Tevkifat uygulanmistir. Genel Toplam 1.000,00 TL")
    assert p.tevkifat is True


def test_detects_istisna_phrase():
    p = parse_invoice_text("KDV istisna kapsamindadir. Toplam 500,00 TL")
    assert p.istisna is True


def test_empty_text_yields_defaults_not_exceptions():
    p = parse_invoice_text("")
    assert p.invoice_type == "paper"
    assert p.vkn is None
    assert p.total_amount is None


def test_bare_vkn_fallback_when_unlabelled():
    p = parse_invoice_text("Firma A.S.\n9876543210\nToplam 100,00 TL")
    assert p.vkn == "9876543210"
