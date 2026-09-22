"""Rule-based Turkish expense categorisation."""
import pytest

from app.services.expense_classifier import CATEGORIES, classify_expense


@pytest.mark.parametrize(
    "text,expected",
    [
        ("Opet akaryakit alimi", "fuel"),
        ("Lokanta yemek gideri", "restaurant"),
        ("Ofis kira odemesi", "rent"),
        ("Elektrik faturasi", "utilities"),
        ("Personel maas odemesi", "payroll"),
        ("KDV vergi odemesi", "tax_payments"),
        ("Microsoft yazilim lisansi", "software"),
        ("Sosyal medya reklam ilani", "marketing"),
        ("Aras kargo gonderi", "shipping"),
        ("THY ucak bileti", "travel"),
        ("Banka havale komisyonu", "bank_fees"),
        ("Kirtasiye toner alimi", "office_supplies"),
        ("Hammadde tedarik", "raw_materials"),
        ("Bilgisayar ekipman alimi", "equipment"),
        ("Klima bakım ve onarım", "maintenance"),
        ("Kasko sigorta policesi", "insurance"),
    ],
)
def test_known_keywords_map_to_category(text, expected):
    assert classify_expense(text) == expected


def test_unknown_text_falls_back_to_other():
    assert classify_expense("zzz belirsiz aciklama") == "other"


def test_vendor_is_considered_alongside_description():
    assert classify_expense(None, vendor="Shell Petrol") == "fuel"


def test_none_inputs_do_not_raise():
    assert classify_expense(None, None) == "other"


def test_result_is_always_a_known_category():
    assert classify_expense("rastgele metin") in CATEGORIES


# ── Fixed behaviour (was F12 / F9) ─────────────────────────────────────
def test_spend_intent_beats_vendor_brand():
    """`marketing` is checked before `software`, so an ad spend on a software
    vendor classifies by what the money was for, not who took it (F12).
    """
    assert classify_expense("Google reklam harcamasi") == "marketing"
    assert classify_expense("Google Workspace lisans") == "software"


def test_classifier_is_diacritic_insensitive():
    """OCR frequently drops Turkish diacritics; both spellings must land in the
    same category (F9). Matching folds ı/ş/ğ/ü/ö/ç on both sides.
    """
    assert classify_expense("Klima bakım ve onarım") == "maintenance"
    assert classify_expense("Klima bakim ve onarim") == "maintenance"
    assert classify_expense("AKARYAKIT ALIMI") == "fuel"
    assert classify_expense("Ofis kirtasiye") == "office_supplies"
