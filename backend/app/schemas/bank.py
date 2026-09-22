"""Schemas for ``/api/bank``.

snake_case across the boundary, like ``/api/compute`` — the browser already
translates its camelCase documents when it builds a snapshot, and one
convention per API is worth more than matching the frontend's.
"""
from __future__ import annotations

import datetime as dt
from typing import Literal

from pydantic import BaseModel, Field

# ── Status & accounts ─────────────────────────────────────────────────


class BankStatusOut(BaseModel):
    """What the Bank screen needs to decide which half of itself to show."""

    provider: str
    display_name: str
    auth: str
    configured: bool
    # True only for a connection that can actually call a bank: the sample
    # provider is "configured" but not live.
    live: bool
    reason: str | None = None
    portal: str | None = None
    base_url: str | None = None
    notes: str | None = None
    # CSV import never depends on a bank connection, so the UI can always
    # offer it.
    csv_import: bool = True


class BankAccountOut(BaseModel):
    id: str
    name: str
    iban: str | None = None
    currency: str = "TRY"
    balance: float | None = None


# ── Movements ─────────────────────────────────────────────────────────


class BankTxnModel(BaseModel):
    """One statement line. Signed: money in positive, money out negative."""

    date: dt.date | None = None
    description: str = ""
    amount: float
    currency: str = "TRY"
    balance: float | None = None
    reference: str | None = None
    counterparty: str | None = None
    category: str = "other"
    source: str = "api"


class BankTxnOut(BankTxnModel):
    direction: Literal["in", "out"] = "out"
    vendor: str = ""
    # The workspace ``transactions`` document this row would become, so the
    # browser can post an unmatched movement to the ledger without rebuilding
    # it and risking a different shape.
    ledger: dict = Field(default_factory=dict)


class InvoiceRefIn(BaseModel):
    """The slice of an invoice the matcher needs, posted by the browser.

    The bank router reads no invoice table for the same reason compute does
    not: the client already holds the workspace and posting the slice keeps
    matching a pure function of its inputs.
    """

    id: str
    amount: float
    date: dt.date | None = None
    vendor: str | None = None
    number: str | None = None
    direction: Literal["sales", "purchase"] = "purchase"
    status: str = "pending"


class MatchOut(BaseModel):
    row_index: int
    invoice_id: str | None = None
    status: Literal["matched", "unmatched"]
    confidence: float = 0.0
    reasons: list[str] = Field(default_factory=list)


class StatementSummary(BaseModel):
    total: int = 0
    matched: int = 0
    unmatched: int = 0
    match_rate: float = 0.0
    money_in: float = 0.0
    money_out: float = 0.0
    net: float = 0.0


# ── Requests ──────────────────────────────────────────────────────────


class FetchRequest(BaseModel):
    account_id: str = ""
    since: dt.date | None = None
    until: dt.date | None = None
    limit: int = Field(default=500, ge=1, le=2000)


class ReconcileRequest(BaseModel):
    rows: list[BankTxnModel] = Field(default_factory=list)
    invoices: list[InvoiceRefIn] = Field(default_factory=list)
    # vendor key -> category, exactly as /api/compute/classify takes it.
    learned: dict[str, str] = Field(default_factory=dict)
    date_window_days: int = Field(default=7, ge=0, le=90)
    amount_tolerance_pct: float = Field(default=0.01, ge=0.0, le=0.25)


class SyncRequest(FetchRequest, ReconcileRequest):
    """Fetch and reconcile in one round trip — what the Bank screen calls."""


# ── Responses ─────────────────────────────────────────────────────────


class TransactionsOut(BaseModel):
    rows: list[BankTxnOut] = Field(default_factory=list)
    summary: StatementSummary = StatementSummary()
    source: Literal["api", "csv", "mock"] = "api"
    account_id: str | None = None
    since: dt.date | None = None
    until: dt.date | None = None


class StatementOut(TransactionsOut):
    matches: list[MatchOut] = Field(default_factory=list)
