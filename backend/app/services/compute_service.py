"""Aggregation for the stateless compute layer.

Turns a :class:`~app.schemas.compute.BusinessSnapshot` — the slice of the workspace
the client sends up — into the inputs each pure engine already expects
(tax, Muhai Score, forecasting, payroll). No DB, no I/O: everything here is a
function of its arguments, which is what makes the whole ``/api/compute``
surface testable without a database.
"""
from __future__ import annotations

import datetime as dt
from collections import defaultdict

from app.schemas.compute import BusinessSnapshot, InvoiceIn, TxnIn
from app.services.expense_classifier import classify_expense
from app.services.muhai_score_service import ScoreInputs

MONTHS_OF_HISTORY = 12


def month_key(d: dt.date) -> str:
    return f"{d.year:04d}-{d.month:02d}"


def month_span(as_of: dt.date, count: int = MONTHS_OF_HISTORY) -> list[str]:
    """The last ``count`` month keys ending at ``as_of``, oldest first."""
    keys: list[str] = []
    year, month = as_of.year, as_of.month
    for _ in range(count):
        keys.append(f"{year:04d}-{month:02d}")
        month -= 1
        if month == 0:
            month = 12
            year -= 1
    return list(reversed(keys))


def monthly_series(
    transactions: list[TxnIn], as_of: dt.date, count: int = MONTHS_OF_HISTORY
) -> list[dict]:
    """Income/expense/profit per month over a fixed, gap-free window."""
    buckets: dict[str, dict[str, float]] = defaultdict(
        lambda: {"income": 0.0, "expense": 0.0}
    )
    for t in transactions:
        buckets[month_key(t.date)][t.type] += float(t.amount)

    series = []
    for key in month_span(as_of, count):
        b = buckets.get(key, {"income": 0.0, "expense": 0.0})
        income = round(b["income"], 2)
        expense = round(b["expense"], 2)
        series.append(
            {
                "month": key,
                "income": income,
                "expense": expense,
                "profit": round(income - expense, 2),
            }
        )
    return series


def _delta(current: float, previous: float) -> float:
    """Percent change, guarding the zero-baseline case."""
    if previous == 0:
        return 100.0 if current > 0 else 0.0
    return round((current - previous) / abs(previous) * 100, 1)


def kpi_block(series: list[dict], tax_current: float, tax_previous: float) -> dict:
    """Headline KPIs for the latest month against the one before it."""
    current = series[-1] if series else {"income": 0.0, "expense": 0.0, "profit": 0.0}
    previous = series[-2] if len(series) > 1 else {"income": 0.0, "expense": 0.0, "profit": 0.0}
    return {
        "revenue": current["income"],
        "revenue_delta": _delta(current["income"], previous["income"]),
        "expense": current["expense"],
        "expense_delta": _delta(current["expense"], previous["expense"]),
        "profit": current["profit"],
        "profit_delta": _delta(current["profit"], previous["profit"]),
        "tax": round(tax_current, 2),
        "tax_delta": _delta(tax_current, tax_previous),
    }


def expense_breakdown(
    transactions: list[TxnIn], as_of: dt.date, months: int = 1
) -> list[dict]:
    """Expense totals per category over the trailing ``months`` window.

    Transactions carrying no category are classified on the fly with the same
    rule engine the ``/api/compute/classify`` endpoint exposes, so an expense
    always lands in a real bucket instead of a silent "uncategorised" hole.
    """
    window = set(month_span(as_of, months))
    totals: dict[str, float] = defaultdict(float)
    for t in transactions:
        if t.type != "expense" or month_key(t.date) not in window:
            continue
        category = t.category or classify_expense(t.description, t.vendor)
        totals[category] += float(t.amount)

    ordered = sorted(totals.items(), key=lambda kv: kv[1], reverse=True)
    return [{"key": k, "value": round(v, 2)} for k, v in ordered]


def daily_net_history(
    transactions: list[TxnIn], as_of: dt.date, days: int = 120
) -> list[tuple[dt.date, float]]:
    """Net cash movement per day, gap-filled, for the forecasting engine.

    Prophet needs an evenly spaced series; days with no movement are real
    zeros, not missing data, so they are emitted explicitly.
    """
    start = as_of - dt.timedelta(days=days - 1)
    net: dict[dt.date, float] = defaultdict(float)
    for t in transactions:
        if start <= t.date <= as_of:
            net[t.date] += float(t.amount) if t.type == "income" else -float(t.amount)

    return [
        (start + dt.timedelta(days=i), round(net.get(start + dt.timedelta(days=i), 0.0), 2))
        for i in range(days)
    ]


def cash_balance(snapshot: BusinessSnapshot) -> float:
    """Explicit balance if the company set one, otherwise net of all movements."""
    if snapshot.cash_balance is not None:
        return round(float(snapshot.cash_balance), 2)
    total = 0.0
    for t in snapshot.transactions:
        total += float(t.amount) if t.type == "income" else -float(t.amount)
    return round(total, 2)


def _is_overdue(inv: InvoiceIn, as_of: dt.date) -> bool:
    if inv.status == "paid":
        return False
    if inv.status == "overdue":
        return True
    return inv.due_date is not None and inv.due_date < as_of


def invoice_rollup(invoices: list[InvoiceIn], as_of: dt.date) -> dict:
    """Receivables, payables and collection performance.

    The overdue tally is split by direction as well as totalled: an overdue
    purchase invoice is money this company owes, and telling its owner to chase
    the customer for it would be advice about the wrong side of the ledger.
    """
    receivables = payables = 0.0
    overdue_count = 0
    overdue_receivables = 0
    overdue_payables = 0
    collected_on_time = 0
    closed = 0

    for inv in invoices:
        if inv.status != "paid":
            if inv.direction == "sales":
                receivables += float(inv.amount)
            else:
                payables += float(inv.amount)
            if _is_overdue(inv, as_of):
                overdue_count += 1
                if inv.direction == "sales":
                    overdue_receivables += 1
                else:
                    overdue_payables += 1
        else:
            closed += 1
            # No due date recorded → treat a paid invoice as collected on time
            # rather than penalising the company for missing metadata.
            if inv.due_date is None or inv.paid_date is None or inv.paid_date <= inv.due_date:
                collected_on_time += 1

    return {
        "receivables": round(receivables, 2),
        "payables": round(payables, 2),
        "overdue_count": overdue_count,
        "overdue_receivable_count": overdue_receivables,
        "overdue_payable_count": overdue_payables,
        "invoices_total": closed,
        "invoices_collected_on_time": collected_on_time,
    }


def score_inputs(snapshot: BusinessSnapshot, as_of: dt.date) -> ScoreInputs:
    """Map a snapshot onto the Muhai Score engine's input dataclass."""
    series = monthly_series(snapshot.transactions, as_of)
    current = series[-1] if series else {"income": 0.0, "expense": 0.0, "profit": 0.0}
    rollup = invoice_rollup(snapshot.invoices, as_of)

    products = snapshot.products
    healthy = sum(1 for p in products if p.stock > p.min_stock)
    payroll = round(sum(float(e.gross_salary) for e in snapshot.employees), 2)

    return ScoreInputs(
        tax_deadlines_total=snapshot.tax_deadlines_total,
        tax_deadlines_on_time=snapshot.tax_deadlines_on_time,
        sgk_payments_total=snapshot.sgk_payments_total,
        sgk_payments_on_time=snapshot.sgk_payments_on_time,
        cash_balance=cash_balance(snapshot),
        monthly_operating_expense=current["expense"],
        total_debt=snapshot.total_debt or rollup["payables"],
        total_assets=snapshot.total_assets or (cash_balance(snapshot) + rollup["receivables"]),
        invoices_total=rollup["invoices_total"],
        invoices_collected_on_time=rollup["invoices_collected_on_time"],
        inventory_items_total=len(products),
        inventory_items_healthy=healthy,
        monthly_payroll=payroll,
        monthly_revenue=current["income"],
        monthly_net_profit=current["profit"],
    )
