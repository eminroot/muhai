"""Vendor extraction and measured confidence.

Both of these were constants before: the vendor was "first mostly-alphabetic
line" and every confidence was a literal, so the review badge read the same
number on a pristine scan and a bad photograph. These tests pin the two
properties that made it meaningless.

Pure functions only — no Tesseract, so they run anywhere.
"""
from app.services.ocr_service import (
    _extract_fields,
    _extract_vendor,
    _score,
    _score_line,
)


# ── Vendor ────────────────────────────────────────────────────────────
def test_the_legal_form_wins_over_position():
    """A photograph puts glare and the document banner above the letterhead.
    Position is the thing a camera disturbs; "A.Ş." is not."""
    vendor, certainty = _extract_vendor(
        ["E-FATURA", "~~ ..", "ANADOLU TEDARIK A.S.", "Bagdat Cad. No:142"]
    )
    assert vendor == "ANADOLU TEDARIK A.S."
    assert certainty == 0.9


def test_turkish_legal_forms_are_recognised():
    for line, expected in [
        ("Teknopark Gayrimenkul A.Ş.", "Teknopark Gayrimenkul A.Ş."),
        ("Ege Ambalaj Ltd. Şti.", "Ege Ambalaj Ltd. Şti."),
        ("Yılmaz San. ve Tic. A.Ş.", "Yılmaz San. ve Tic. A.Ş."),
    ]:
        vendor, certainty = _extract_vendor(["FATURA", line, "Vergi No: 1"])
        assert vendor == expected
        assert certainty == 0.9


def test_document_banners_are_never_the_vendor():
    for banner in ["FATURA", "E-ARŞİV FATURA", "İRSALİYE", "SAYIN", "MAKBUZ"]:
        vendor, _ = _extract_vendor([banner, "Ege Ambalaj Ltd. Şti."])
        assert vendor == "Ege Ambalaj Ltd. Şti."


def test_a_name_without_a_legal_form_is_still_offered_but_doubted():
    """A sole trader has no "A.Ş.". Returning nothing would be worse than
    guessing, so long as the guess says it is one."""
    vendor, certainty = _extract_vendor(["Mehmet Yılmaz", "Bağdat Cad"])
    assert vendor == "Mehmet Yılmaz"
    assert certainty == 0.5


def test_nothing_usable_scores_zero():
    assert _extract_vendor(["123", ".."]) == (None, 0.0)


# ── Confidence ────────────────────────────────────────────────────────
def test_confidence_falls_when_the_page_reads_badly():
    clean = _score(0.9, {"ANADOLU TEDARIK A.S.": 0.95}, "ANADOLU TEDARIK A.S.")
    poor = _score(0.9, {"ANADOLU TEDARIK A.S.": 0.45}, "ANADOLU TEDARIK A.S.")
    assert clean > poor
    assert poor < 0.5


def test_an_engine_without_confidence_falls_back_to_the_rule():
    """A cloud OCR provider need not implement image_to_lines()."""
    assert _score(0.9, {}, "X") == 0.9


def test_a_missing_field_scores_zero_however_clean_the_page():
    assert _score(0.9, {"whatever": 1.0}, None) == 0.0


def test_amounts_are_scored_from_their_own_line():
    """The parsed float (14820.0) never appears in the text ("14.820,00"), so
    the amount fields have to carry their source line or they silently keep
    the old hardcoded number."""
    line = "GENEL TOPLAM: 14.820,00"
    assert _score_line(0.8, {line: 0.5}, line, 14820.0) == 0.4
    assert _score_line(0.8, {line: 1.0}, line, 14820.0) == 0.8


def test_fields_are_measured_end_to_end():
    text = "\n".join(
        [
            "FATURA",
            "ANADOLU TEDARIK A.S.",
            "Fatura No: AND-2026-8842",
            "Fatura Tarihi: 05.09.2026",
            "Hesaplanan KDV %20: 2.470,00",
            "GENEL TOPLAM: 14.820,00",
        ]
    )
    crisp = _extract_fields(text, {ln: 0.95 for ln in text.splitlines()})
    smudged = _extract_fields(text, {ln: 0.40 for ln in text.splitlines()})

    assert crisp.vendor_name.value == "ANADOLU TEDARIK A.S."
    assert crisp.total_amount.value == 14820.0
    assert crisp.vat_amount.value == 2470.0

    # Same text, same fields — only the reading quality differs, and every
    # field has to notice.
    for field in ("vendor_name", "invoice_number", "date", "total_amount", "vat_amount"):
        assert getattr(crisp, field).confidence > getattr(smudged, field).confidence, field
    assert smudged.needs_review is True
