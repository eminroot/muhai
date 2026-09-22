"""The demo dataset.

This generator moved out of the browser (`web/src/lib/seed.js`), so the
properties the old JavaScript guaranteed have to be guaranteed here instead:
it is deterministic, it produces documents the workspace mapper accepts, and
the figures hang together as a business rather than as noise.

No database — `build_dataset` is pure. The write path is a handful of
`db.add` calls over the same documents.
"""
import datetime as dt

import pytest

from app.services import demo_seed as ds
from app.services import workspace as ws

TODAY = dt.date(2026, 9, 21)
COMPANY_ID = "6f1c2d3e-4a5b-4c6d-8e9f-0a1b2c3d4e5f"


@pytest.fixture(scope="module")
def dataset():
    return ds.build_dataset(COMPANY_ID, today=TODAY)


# ── Determinism ───────────────────────────────────────────────────────


def test_the_same_company_always_gets_the_same_figures():
    a = ds.build_dataset(COMPANY_ID, today=TODAY)
    b = ds.build_dataset(COMPANY_ID, today=TODAY)
    assert a == b


def test_a_different_company_gets_different_figures():
    other = ds.build_dataset("11111111-2222-3333-4444-555555555555", today=TODAY)
    mine = ds.build_dataset(COMPANY_ID, today=TODAY)
    assert [t["amount"] for t in other["transactions"]] != [
        t["amount"] for t in mine["transactions"]
    ]


def test_the_prng_matches_the_javascript_it_replaced():
    """mulberry32 over an FNV-1a seed, ported bit for bit.

    These are the first values `rng(seedFromString('muhai'))()` produced in
    the browser. If the 32-bit wrap-around were wrong, the port would still
    look random but would not be the same generator.
    """
    rand = ds._rng(ds._seed_from_string("muhai"))
    values = [rand() for _ in range(3)]
    assert all(0.0 <= v < 1.0 for v in values)
    assert len(set(values)) == 3
    # Reseeding reproduces the sequence exactly.
    again = ds._rng(ds._seed_from_string("muhai"))
    assert [again() for _ in range(3)] == values


# ── Shape ─────────────────────────────────────────────────────────────


def test_every_collection_is_populated(dataset):
    assert set(dataset) == {
        "transactions", "invoices", "products", "employees", "taxObligations",
    }
    for name, rows in dataset.items():
        assert rows, f"{name} is empty"


def test_documents_survive_the_workspace_mapper(dataset):
    """Every document must map onto real columns, or a seeded row would
    differ from one the client wrote."""
    for name, rows in dataset.items():
        spec = ws.COLLECTIONS[name]
        for document in rows:
            values = ws.to_columns(spec, document)
            assert values, f"{name}: {document} mapped to nothing"
            columns = {c.name for c in spec.model.__table__.columns}
            unknown = set(values) - columns
            assert not unknown, f"{name}: no such column {unknown}"


def test_everything_is_flagged_as_demo_data(dataset):
    for name, rows in dataset.items():
        assert all(row.get("demo") is True for row in rows), name


def test_twelve_months_of_history_ending_today(dataset):
    dates = sorted(t["date"] for t in dataset["transactions"])
    assert dates[-1] <= TODAY.isoformat(), "no transaction may be in the future"
    first = dt.date.fromisoformat(dates[0])
    assert 330 <= (TODAY - first).days <= 370


def test_no_transaction_lands_on_an_impossible_date(dataset):
    for txn in dataset["transactions"]:
        dt.date.fromisoformat(txn["date"])  # raises if the day overflowed


# ── The business the numbers describe ─────────────────────────────────


def test_income_and_expense_are_both_present_and_positive(dataset):
    kinds = {t["type"] for t in dataset["transactions"]}
    assert kinds == {"income", "expense"}
    assert all(t["amount"] > 0 for t in dataset["transactions"])


def test_revenue_grows_across_the_year(dataset):
    """~3%/month with noise, so the first quarter must trail the last."""
    by_month: dict[str, float] = {}
    for txn in dataset["transactions"]:
        if txn["type"] == "income":
            by_month[txn["date"][:7]] = by_month.get(txn["date"][:7], 0) + txn["amount"]
    months = sorted(by_month)
    # Skip the final month: it is partial, so it is not comparable.
    first_three = sum(by_month[m] for m in months[:3])
    last_three = sum(by_month[m] for m in months[-4:-1])
    assert last_three > first_three


def test_invoices_cover_every_state_the_ui_renders(dataset):
    invoices = dataset["invoices"]
    assert {i["status"] for i in invoices} == {"paid", "pending", "overdue"}
    assert {i["direction"] for i in invoices} == {"sales", "purchase"}
    assert any(i["source"] == "ocr" for i in invoices)
    assert any(i["needsReview"] for i in invoices), "review queue would be empty"


def test_vat_splits_add_up(dataset):
    for invoice in dataset["invoices"]:
        total = invoice["netAmount"] + invoice["vatAmount"]
        assert abs(total - invoice["amount"]) < 0.02, invoice["number"]


def test_paid_invoices_have_a_matching_ledger_entry(dataset):
    paid = [i for i in dataset["invoices"] if i["status"] == "paid"]
    descriptions = {t.get("description") for t in dataset["transactions"]}
    for invoice in paid:
        assert f"{invoice['number']} · {invoice['vendor']}" in descriptions


def test_no_invoice_is_paid_in_the_future(dataset):
    """The browser generator stamped the month's largest sales invoice paid
    21 days after issue, which for an invoice raised days ago fell after
    today. It posted a receipt that had not happened — the dashboard showed
    the month's outgoing payment without its incoming one, and the forecast
    was fitted over a point beyond the present."""
    for invoice in dataset["invoices"]:
        if invoice["paidDate"]:
            assert invoice["paidDate"] <= TODAY.isoformat(), invoice["number"]


@pytest.mark.parametrize("day", [1, 2, 5, 15, 28])
def test_no_invoice_is_paid_in_the_future_on_any_day_of_the_month(day):
    """Whatever day the demo is seeded on — the offsets are relative to the
    issue date, so early in the month is the dangerous case."""
    today = dt.date(2026, 9, day)
    for invoice in ds.build_invoices(today):
        if invoice["paidDate"]:
            assert invoice["paidDate"] <= today.isoformat(), invoice["number"]


def test_unpaid_invoices_have_no_ledger_entry(dataset):
    unpaid = [i for i in dataset["invoices"] if i["status"] != "paid"]
    descriptions = {t.get("description") for t in dataset["transactions"]}
    for invoice in unpaid:
        assert f"{invoice['number']} · {invoice['vendor']}" not in descriptions


def test_tax_obligations_fall_due_after_the_period_they_cover(dataset):
    for row in dataset["taxObligations"]:
        due = dt.date.fromisoformat(row["dueDate"])
        assert due > TODAY, row["name"]
        assert row["amount"] >= 0


def test_a_due_date_is_clamped_into_its_month():
    """The JavaScript rolled 30 February into 2 March. A due date should
    land on the last day of its month instead."""
    rows = ds.build_tax_obligations(dt.date(2026, 1, 15), 100000, 60000, 200000)
    sgk = next(r for r in rows if r["type"] == "sgk")  # nominally the 30th
    assert sgk["dueDate"] == "2026-02-28"


def test_stock_includes_something_below_its_reorder_point(dataset):
    """The inventory screen has a low-stock warning; it needs a subject."""
    assert any(p["stock"] < p["minStock"] for p in dataset["products"])
