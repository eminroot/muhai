"""The statement pipeline: parse, normalise, categorise, reconcile.

Pure functions, no database, no network. The bank payloads below are written
in the shapes that actually cause trouble — Turkish decimals, a borç/alacak
flag, a nested amount object, an ISO 20022 indicator — because a normaliser
that only handles the tidy shape is a normaliser that fails on the first real
bank.
"""
import datetime as dt

import pytest

from app.services import bank_service as bs
from app.services.bank_providers import FieldMap

TODAY = dt.date(2026, 9, 20)


# ── Numbers and dates ─────────────────────────────────────────────────


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("1.234,56", 1234.56),      # Turkish
        ("1,234.56", 1234.56),      # English
        ("18.880,00", 18880.0),
        ("120,50", 120.5),
        ("1,234", 1234.0),          # a lone comma grouping thousands
        ("-450,25", -450.25),
        ("450,25-", -450.25),       # trailing minus: statement convention
        ("1.500 TL", 1500.0),   # a lone dot grouping thousands
        ("2500.55", 2500.55),  # ...but two trailing digits are decimals
        (2500, 2500.0),
        (12.344, 12.34),
        ("", None),
        ("   ", None),
        (None, None),
        ("abc", None),
    ],
)
def test_parse_amount_reads_every_convention(raw, expected):
    assert bs.parse_amount(raw) == expected


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("2026-09-05", dt.date(2026, 9, 5)),
        ("05.09.2026", dt.date(2026, 9, 5)),
        ("05/09/2026", dt.date(2026, 9, 5)),
        ("20260905", dt.date(2026, 9, 5)),
        ("2026-09-05T14:31:00Z", dt.date(2026, 9, 5)),
        ("05.09.2026 14:31", dt.date(2026, 9, 5)),
        ("", None),
        ("not a date", None),
    ],
)
def test_parse_date_reads_every_convention(raw, expected):
    assert bs.parse_date(raw) == expected


# ── Tolerant lookup ───────────────────────────────────────────────────


def test_pick_is_case_and_diacritic_insensitive():
    record = {"İşlem Tarihi": "2026-09-05", "AÇIKLAMA": "KIRA"}
    assert bs.pick(record, ("islemTarihi",)) == "2026-09-05"
    assert bs.pick(record, ("aciklama",)) == "KIRA"


def test_pick_descends_into_nested_objects():
    record = {"transactionAmount": {"value": "120,50", "currency": "TRY"}}
    assert bs.pick(record, ("amount", "transactionAmount")) == "120,50"


def test_pick_follows_a_dotted_candidate():
    record = {"detail": {"info": {"text": "FATURA"}}}
    assert bs.pick(record, ("detail.info.text",)) == "FATURA"


def test_extract_list_finds_the_array_however_it_is_wrapped():
    assert len(bs.extract_list({"data": {"transactions": [{"a": 1}]}}, ("data.transactions",))) == 1
    assert len(bs.extract_list({"hesapHareketleri": [{"a": 1}, {"b": 2}]}, ("hesapHareketleri",))) == 2
    assert len(bs.extract_list([{"a": 1}], ("",))) == 1
    # Unknown wrapper: fall back to the first list of objects in the body.
    assert len(bs.extract_list({"payload": {"weirdName": [{"a": 1}]}}, ("",))) == 1
    assert bs.extract_list({"message": "no rows"}, ("data",)) == []


# ── Normalising three different banks ─────────────────────────────────


def test_normalize_iso20022_shape():
    records = [
        {
            "bookingDate": "2026-09-05",
            "transactionAmount": {"amount": "1250.00", "currency": "TRY"},
            "creditDebitIndicator": "DBIT",
            "remittanceInformation": "OFIS KIRA ODEMESI",
            "creditorName": "Teknopark Gayrimenkul A.S.",
        }
    ]
    row = bs.normalize_records(records, FieldMap())[0]
    assert row.date == dt.date(2026, 9, 5)
    assert row.amount == -1250.0  # DBIT is money leaving
    assert row.direction == "out"
    assert row.counterparty == "Teknopark Gayrimenkul A.S."


def test_normalize_turkish_borc_alacak_flag():
    records = [
        {"islemTarihi": "05.09.2026", "tutar": "18.880,00", "borcAlacakKodu": "A", "aciklama": "FAST GELEN"},
        {"islemTarihi": "06.09.2026", "tutar": "3.417,50", "borcAlacakKodu": "B", "aciklama": "ELEKTRIK"},
    ]
    incoming, outgoing = bs.normalize_records(records)
    assert incoming.amount == 18880.0
    assert outgoing.amount == -3417.5


def test_normalize_separate_debit_and_credit_columns():
    records = [{"tarih": "2026-09-05", "borc": "500,00", "alacak": "", "aciklama": "KOMISYON"}]
    assert bs.normalize_records(records)[0].amount == -500.0


def test_normalize_drops_rows_without_an_amount():
    records = [{"tarih": "2026-09-05", "aciklama": "DEVIR BAKIYESI"}]
    assert bs.normalize_records(records) == []


def test_field_map_override_wins_and_keeps_the_defaults():
    fields = FieldMap().merged({"description": "ourOwnLabel"})
    assert fields.description[0] == "ourOwnLabel"
    assert "aciklama" in fields.description

    row = bs.normalize_records([{"tarih": "2026-09-05", "tutar": "-100", "ourOwnLabel": "X"}], fields)[0]
    assert row.description == "X"


def test_normalize_accounts():
    accounts = bs.normalize_accounts(
        [{"accountId": "TR11", "hesapAdi": "Vadesiz", "iban": "TR11", "bakiye": "10.000,00"}]
    )
    assert accounts == [
        {"id": "TR11", "name": "Vadesiz", "iban": "TR11", "currency": "TRY", "balance": 10000.0}
    ]


# ── CSV import ────────────────────────────────────────────────────────

TURKISH_CSV = """Tarih;Açıklama;Tutar;Bakiye
05.09.2026;KIRA ÖDEMESİ - TEKNOPARK;-24.500,00;120.000,00
06.09.2026;FAST GELEN - ACME TEKNOLOJİ A.Ş.;18.880,00;138.880,00
"""

DEBIT_CREDIT_CSV = """Date,Description,Debit,Credit
2026-09-05,ELEKTRIK FATURASI,3417.50,
2026-09-06,POS TAHSILATI,,4250.75
"""


def test_parse_turkish_semicolon_csv():
    rows = bs.parse_bank_csv(TURKISH_CSV)
    assert [r.amount for r in rows] == [-24500.0, 18880.0]
    assert rows[0].date == dt.date(2026, 9, 5)
    assert rows[0].balance == 120000.0
    assert rows[0].source == "csv"


def test_parse_csv_with_debit_and_credit_columns():
    rows = bs.parse_bank_csv(DEBIT_CREDIT_CSV)
    assert [r.amount for r in rows] == [-3417.5, 4250.75]


def test_parse_csv_survives_a_byte_order_mark_and_empty_input():
    assert len(bs.parse_bank_csv("﻿" + TURKISH_CSV)) == 2
    assert bs.parse_bank_csv("") == []
    assert bs.parse_bank_csv("no columns here") == []


# ── Categorisation ────────────────────────────────────────────────────


def _txn(description, amount, counterparty=None, day=5):
    return bs.BankTxn(
        date=dt.date(2026, 9, day), description=description, amount=amount, counterparty=counterparty
    )


def test_categorise_uses_the_bank_specific_rules_first():
    assert bs.categorise(_txn("KDV ODEMESI - GIB", -9240)) == "tax_payments"
    assert bs.categorise(_txn("MAAS ODEMESI - PERSONEL", -112000)) == "payroll"
    assert bs.categorise(_txn("HESAP ISLETIM UCRETI", -185)) == "bank_fees"


def test_categorise_falls_through_to_the_expense_classifier():
    assert bs.categorise(_txn("ELEKTRIK FATURASI - ENERJISA", -3417)) == "utilities"
    assert bs.categorise(_txn("KIRA ODEMESI", -24500)) == "rent"


def test_how_the_money_moved_is_not_what_it_was_spent_on():
    """A supplier paid by EFT is a supplier payment, not a bank fee. The
    mechanism words lead every statement line, so they are stripped before the
    expense classifier sees the text."""
    assert bs.categorise(_txn("EFT GIDEN - EGE AMBALAJ SAN. TIC.", -92300)) == "other"
    assert bs.categorise(_txn("HAVALE - KIRA ODEMESI", -24500)) == "rent"
    # ...but a fee that names itself is still a fee.
    assert bs.categorise(_txn("HAVALE KOMISYONU", -18)) == "bank_fees"


def test_a_learned_vendor_beats_the_keyword_rules():
    row = _txn("AYLIK ODEME", -1000, counterparty="Acme Teknoloji A.Ş.")
    learned = {"acme teknoloji as": "software"}
    assert bs.categorise(row, learned) == "software"


def test_incoming_money_is_not_given_an_expense_category():
    assert bs.categorise(_txn("FAST GELEN - ACME", 18880)) == "other"


def test_categorise_all_normalises_the_learned_keys():
    rows = [_txn("ODEME", -500, counterparty="ACME TEKNOLOJİ A.Ş.")]
    bs.categorise_all(rows, {"Acme Teknoloji A.Ş.": "marketing"})
    assert rows[0].category == "marketing"


# ── Reconciliation ────────────────────────────────────────────────────


def _invoice(id_, amount, day, vendor, direction="purchase", number=None):
    return bs.InvoiceRef(
        id=id_, amount=amount, date=dt.date(2026, 9, day), vendor=vendor,
        number=number, direction=direction,
    )


def test_a_payment_matches_its_purchase_invoice():
    rows = [_txn("KIRA ODEMESI - TEKNOPARK GAYRIMENKUL AS", -24500.0, day=7)]
    invoices = [_invoice("inv1", 24500.0, 5, "Teknopark Gayrimenkul A.Ş.")]

    match = bs.reconcile(rows, invoices)[0]
    assert match.status == "matched"
    assert match.invoice_id == "inv1"
    assert "vendor" in match.reasons and "date" in match.reasons


def test_a_collection_matches_its_sales_invoice():
    rows = [_txn("FAST GELEN - ACME TEKNOLOJI", 18880.0, day=6)]
    invoices = [_invoice("inv2", 18880.0, 5, "Acme Teknoloji A.Ş.", direction="sales")]
    assert bs.reconcile(rows, invoices)[0].invoice_id == "inv2"


def test_direction_must_agree():
    """Money going out cannot be settling a sales invoice, however well the
    amount and the name line up."""
    rows = [_txn("ACME TEKNOLOJI", -18880.0, day=6)]
    invoices = [_invoice("inv2", 18880.0, 5, "Acme Teknoloji", direction="sales")]
    assert bs.reconcile(rows, invoices)[0].status == "unmatched"


def test_a_payment_outside_the_date_window_is_not_matched():
    rows = [_txn("TEKNOPARK", -24500.0, day=25)]
    invoices = [_invoice("inv1", 24500.0, 1, "Teknopark")]
    assert bs.reconcile(rows, invoices)[0].status == "unmatched"
    assert bs.reconcile(rows, invoices, date_window_days=40)[0].status == "matched"


def test_an_invoice_number_in_the_description_lifts_confidence():
    rows = [_txn("ODEME FATURA 2026-0041", -1000.0, day=5)]
    invoices = [_invoice("inv9", 1000.0, 5, "Bilinmeyen", number="2026-0041")]
    match = bs.reconcile(rows, invoices)[0]
    assert "invoice_no" in match.reasons
    assert match.confidence > 0.8


def test_the_best_pair_wins_rather_than_the_first_one_read():
    """Two invoices, same amount, same week. The vendor name decides which
    payment settles which — not the order the rows arrived in."""
    rows = [
        _txn("ODEME - BETA LOJISTIK", -5000.0, day=5),
        _txn("ODEME - ACME TEKNOLOJI", -5000.0, day=5),
    ]
    invoices = [
        _invoice("acme", 5000.0, 4, "Acme Teknoloji"),
        _invoice("beta", 5000.0, 4, "Beta Lojistik"),
    ]
    matches = bs.reconcile(rows, invoices)
    assert matches[0].invoice_id == "beta"
    assert matches[1].invoice_id == "acme"


def test_one_invoice_is_never_matched_twice():
    rows = [_txn("ODEME - ACME", -5000.0, day=5), _txn("ODEME - ACME", -5000.0, day=6)]
    invoices = [_invoice("acme", 5000.0, 4, "Acme")]
    matches = bs.reconcile(rows, invoices)
    assert [m.status for m in matches] == ["matched", "unmatched"]


def test_small_rounding_differences_still_match():
    rows = [_txn("ODEME - ACME", -1000.40, day=5)]
    invoices = [_invoice("acme", 1000.0, 5, "Acme")]
    assert bs.reconcile(rows, invoices)[0].status == "matched"


def test_summary_counts_both_directions():
    rows = [_txn("A", 100.0), _txn("B", -40.0)]
    matches = bs.reconcile(rows, [])
    summary = bs.summarise(rows, matches)
    assert summary == {
        "total": 2, "matched": 0, "unmatched": 2, "match_rate": 0.0,
        "money_in": 100.0, "money_out": 40.0, "net": 60.0,
    }


def test_an_unmatched_row_becomes_a_ledger_document():
    row = _txn("ELEKTRIK FATURASI", -3417.5, counterparty="Enerjisa")
    row.category = bs.categorise(row)
    assert bs.to_transaction_document(row) == {
        "date": "2026-09-05",
        "amount": 3417.5,
        "type": "expense",
        "category": "utilities",
        "description": "ELEKTRIK FATURASI",
        "vendor": "Enerjisa",
        "source": "bank",
    }


def test_incoming_money_becomes_an_income_entry():
    assert bs.to_transaction_document(_txn("TAHSILAT", 4250.75))["type"] == "income"
