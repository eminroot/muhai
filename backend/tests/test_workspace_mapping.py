"""Document ⇄ row mapping for the company workspace.

The whole web app is written against document shapes that used to be Firestore
documents. If this mapping loses a field, coerces a number wrongly, or drops an
unrecognised key, nothing raises — the dashboard just shows the wrong money.
So the round trip is tested directly, without a database: the mapping is pure.
"""
import datetime as dt

import pytest

from app.services import workspace as ws


class Row:
    """Stand-in for an ORM row: attributes, plus the extra/created_at pair."""

    def __init__(self, **values):
        self.extra = {}
        self.created_at = None
        for key, value in values.items():
            setattr(self, key, value)


def _row_from(spec: ws.Collection, document: dict) -> Row:
    """Build a row the way the database would: every column present.

    ``to_columns`` returns only the keys the document carried — that is what
    makes it usable for a PATCH — so the absent ones are filled in here, as a
    real INSERT would fill them from their defaults.
    """
    values = {column: None for column in spec.columns.values()}
    values.update(ws.to_columns(spec, document))
    return Row(id="row-1", **values)


INVOICE = {
    "number": "MUH-2026-0001",
    "vendor": "Anadolu Tedarik A.Ş.",
    "taxId": "4830027561",
    "direction": "sales",
    "issueDate": "2026-06-04",
    "dueDate": "2026-07-04",
    "paidDate": "2026-06-25",
    "amount": 148200,
    "netAmount": 123500,
    "vatAmount": 24700,
    "status": "paid",
    "category": "sales",
    "source": "manual",
    "ocrConfidence": None,
    "needsReview": False,
}


def test_invoice_round_trips_unchanged():
    spec = ws.COLLECTIONS["invoices"]
    row = _row_from(spec, INVOICE)
    document = ws.to_document(spec, row)

    for key, value in INVOICE.items():
        assert document[key] == value, key
    assert document["id"] == "row-1"


def test_dates_become_dates_and_come_back_as_iso_strings():
    """Calendar dates cross the boundary unchanged — no timezone drift."""
    spec = ws.COLLECTIONS["invoices"]
    row = _row_from(spec, INVOICE)

    assert row.issue_date == dt.date(2026, 6, 4)
    assert ws.to_document(spec, row)["issueDate"] == "2026-06-04"


def test_unknown_keys_survive_in_extra():
    spec = ws.COLLECTIONS["invoices"]
    row = _row_from(spec, {**INVOICE, "vatRate": 0.2, "currency": "TRY"})

    assert row.extra == {"vatRate": 0.2, "currency": "TRY"}
    document = ws.to_document(spec, row)
    assert document["vatRate"] == 0.2
    assert document["currency"] == "TRY"


def test_patch_only_touches_the_keys_it_carries():
    spec = ws.COLLECTIONS["invoices"]
    row = _row_from(spec, INVOICE)

    ws.apply_patch(spec, row, {"status": "pending"})

    assert row.status == "pending"
    assert row.vendor == "Anadolu Tedarik A.Ş."
    assert row.amount == 148200


def test_patching_one_extra_key_keeps_the_others():
    """extra is merged, not replaced — the trap a naive setattr would fall in."""
    spec = ws.COLLECTIONS["invoices"]
    row = _row_from(spec, {**INVOICE, "vatRate": 0.2, "currency": "TRY"})

    ws.apply_patch(spec, row, {"vatRate": 0.1})

    assert row.extra == {"vatRate": 0.1, "currency": "TRY"}


def test_server_managed_keys_are_never_written_from_a_document():
    """A client cannot re-parent a row by posting a companyId."""
    spec = ws.COLLECTIONS["transactions"]
    columns = ws.to_columns(
        spec,
        {"date": "2026-06-01", "amount": 100, "companyId": "someone-else", "id": "x"},
    )

    assert "company_id" not in columns
    assert "id" not in columns
    assert columns.get("extra") is None


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("1234.50", 1234.50),
        (1234.5, 1234.5),
        ("", 0.0),
        (None, 0.0),
        ("not a number", 0.0),
    ],
)
def test_amounts_coerce_rather_than_raise(raw, expected):
    """One malformed figure must not fail a 400-row seeding batch."""
    spec = ws.COLLECTIONS["transactions"]
    assert ws.to_columns(spec, {"amount": raw})["amount"] == expected


def test_an_unparseable_date_becomes_null_not_an_error():
    spec = ws.COLLECTIONS["transactions"]
    assert ws.to_columns(spec, {"date": "yesterday"})["date"] is None


def test_every_collection_the_client_uses_is_mapped():
    """The five collections DataContext subscribes to, and no stragglers."""
    assert set(ws.COLLECTION_NAMES) == {
        "invoices",
        "transactions",
        "products",
        "employees",
        "taxObligations",
        "vendorCategories",
    }


@pytest.mark.parametrize("name", ws.COLLECTION_NAMES)
def test_each_collection_maps_onto_real_columns(name):
    """Catches a field map that drifted from its model."""
    spec = ws.COLLECTIONS[name]
    for document_key, column in spec.columns.items():
        assert hasattr(spec.model, column), f"{name}.{document_key} -> {column}"


def test_company_profile_round_trips():
    company = Row(
        id="c1",
        name="Atlas Ticaret Ltd. Şti.",
        tax_id="4830027561",
        tax_office="Kadıköy",
        sector="logistics",
        city="İstanbul",
        email="owner@example.com",
        legal_form="ltd",
        currency="TRY",
        cash_balance=180000,
        seeded=True,
        seeded_at="2026-09-08T00:00:00",
        owner_user_id="u1",
    )
    document = ws.company_document(company)

    assert document["name"] == "Atlas Ticaret Ltd. Şti."
    assert document["cashBalance"] == 180000
    assert document["taxOffice"] == "Kadıköy"
    assert document["ownerUid"] == "u1"
