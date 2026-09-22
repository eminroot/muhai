"""Schemas for the stateless ``/api/compute`` layer.

The workspace holds the data; the client posts the slice it needs analysed and gets
computed results back. Nothing here touches the database, so every endpoint is
a pure function of its request body.
"""
from __future__ import annotations

import datetime as dt
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# ── Shared input records (mirrors of the workspace documents) ──────────


class TxnIn(BaseModel):
    """One income/expense movement."""

    date: dt.date
    amount: float = Field(ge=0)
    type: Literal["income", "expense"]
    category: str | None = None
    description: str | None = None
    vendor: str | None = None


class InvoiceIn(BaseModel):
    # id and number are carried only for the compliance checks, which report
    # *which* document tripped a rule. Every other engine ignores them.
    id: str | None = None
    number: str | None = None
    date: dt.date | None = None
    due_date: dt.date | None = None
    paid_date: dt.date | None = None
    amount: float = 0.0
    vat_amount: float = 0.0
    vendor: str | None = None
    status: Literal["paid", "pending", "overdue"] = "pending"
    direction: Literal["sales", "purchase"] = "purchase"


class ProductIn(BaseModel):
    name: str
    stock: float = 0.0
    min_stock: float = 0.0
    unit_price: float = 0.0
    monthly_usage: float = 0.0


class EmployeeIn(BaseModel):
    name: str
    gross_salary: float = 0.0
    start_date: dt.date | None = None


class BusinessSnapshot(BaseModel):
    """Everything the compute layer needs about one company."""

    as_of: dt.date | None = None
    cash_balance: float | None = None
    transactions: list[TxnIn] = Field(default_factory=list)
    invoices: list[InvoiceIn] = Field(default_factory=list)
    products: list[ProductIn] = Field(default_factory=list)
    employees: list[EmployeeIn] = Field(default_factory=list)
    tax_deadlines_total: int = 0
    tax_deadlines_on_time: int = 0
    sgk_payments_total: int = 0
    sgk_payments_on_time: int = 0
    total_debt: float = 0.0
    total_assets: float = 0.0


# ── Dashboard ──────────────────────────────────────────────────────────


class MonthPoint(BaseModel):
    month: str  # ISO "YYYY-MM"
    income: float
    expense: float
    profit: float


class CategoryPoint(BaseModel):
    key: str
    value: float


class KpiBlock(BaseModel):
    revenue: float
    revenue_delta: float
    expense: float
    expense_delta: float
    profit: float
    profit_delta: float
    tax: float
    tax_delta: float


class DeadlineOut(BaseModel):
    type: str
    name: str
    due_date: dt.date
    days_remaining: int
    is_due_soon: bool


class DashboardOut(BaseModel):
    kpis: KpiBlock
    monthly: list[MonthPoint]
    expense_breakdown: list[CategoryPoint]
    cash_balance: float
    receivables: float
    payables: float
    overdue_count: float
    deadlines: list[DeadlineOut]
    insight: str


# ── Compliance ──────────────────────────────────────────────────────


class ComplianceAlertItem(BaseModel):
    """One rule violation the engine found in the posted snapshot.

    ``description`` is Turkish, like the dashboard's ``insight`` — the rule
    engine writes the specific sentence (which invoice, how many days) and the
    client localises only the heading it sits under.
    """

    type: Literal["duplicate_invoice", "suspicious_invoice", "tax_deadline"]
    severity: Literal["high", "medium", "low"]
    description: str
    ref_id: str | None = None


class ComplianceOut(BaseModel):
    alerts: list[ComplianceAlertItem]
    total: int
    high: int
    medium: int
    low: int


# ── Muhai Score ────────────────────────────────────────────────────────


class CategoryScoreOut(BaseModel):
    key: str
    label: str
    weight: float
    score: float
    points: float


class MuhaiScoreOut(BaseModel):
    total_score: int
    rating: str
    cash_runway_days: float
    categories: list[CategoryScoreOut]
    strengths: list[str]
    risks: list[str]
    recommendations: list[str]


# ── Forecast ───────────────────────────────────────────────────────────


class ForecastPoint(BaseModel):
    """One predicted day. Produced by ``forecast_service``; ``ForecastPointOut``
    below is the same shape as the API returns it."""

    ds: dt.date
    yhat: float
    yhat_lower: float
    yhat_upper: float


class ForecastPointOut(BaseModel):
    ds: dt.date
    yhat: float
    yhat_lower: float
    yhat_upper: float


class ForecastOut(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    points: list[ForecastPointOut]
    engine: Literal["prophet", "moving_average"]
    horizon_days: int
    history_points: int
    projected_net: float
    projected_balance: float


# ── Tax ────────────────────────────────────────────────────────────────


class TaxSummaryOut(BaseModel):
    period: str
    kdv_collected: float
    kdv_paid: float
    kdv_payable: float
    revenue: float
    expenses: float
    profit: float
    corporate_tax: float
    corporate_quarterly: float
    stopaj_rent: float
    total_due: float
    deadlines: list[DeadlineOut]


# ── Payroll ────────────────────────────────────────────────────────────


class PayslipOut(BaseModel):
    name: str
    gross_salary: float
    sgk_employee: float
    unemployment_employee: float
    income_tax: float
    stamp_tax: float
    total_deductions: float
    net_salary: float
    sgk_employer: float
    unemployment_employer: float
    total_employer_cost: float
    tenure_years: float
    severance_estimate: float
    annual_leave_days: int


class PayrollRunOut(BaseModel):
    payslips: list[PayslipOut]
    total_gross: float
    total_net: float
    total_deductions: float
    total_employer_cost: float
    headcount: int


# ── Expense classification ─────────────────────────────────────────────


class ClassifyItem(BaseModel):
    id: str | None = None
    description: str | None = None
    vendor: str | None = None
    amount: float = 0.0


class ClassifyBatchRequest(BaseModel):
    items: list[ClassifyItem]
    # What this company has already taught the classifier: normalised vendor
    # key -> category. The browser holds it (it is workspace data) and posts it
    # with the request, which is how learning works without the compute layer
    # ever reading a table.
    learned: dict[str, str] = Field(default_factory=dict)


class ClassifiedItem(BaseModel):
    id: str | None = None
    category: str
    source: Literal["learned", "rules"] = "rules"


class ClassifyBatchResponse(BaseModel):
    items: list[ClassifiedItem]
    categories: list[str]


# ── Chat ───────────────────────────────────────────────────────────────


class ComputeChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    snapshot: BusinessSnapshot | None = None
    lang: Literal["tr", "en"] = "tr"


class ComputeChatResponse(BaseModel):
    reply: str
    source: Literal["placeholder", "ai", "offline"]
