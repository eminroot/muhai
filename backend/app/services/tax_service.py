"""Turkey tax & payroll formula engine (Module 2 — Smart Turkish Tax Engine).

Pure functions — no DB, no side effects — so they are trivially unit-testable
and can later be swapped for a region-aware rules engine without touching the
API contracts.

All rates are the **official 2026** values. These are legal numbers: do not
guess or round them away. A reusable :class:`TaxEngine` facade is provided at the
bottom for callers (API routes, chatbot, predictions) that prefer an object.
"""
from dataclasses import asdict, dataclass
from typing import Literal

# ── KDV / VAT rates (2026) ─────────────────────────────────────────────
VAT_STANDARD = 0.20  # standard rate
VAT_REDUCED = 0.10  # reduced rate (textiles, hotel, cinema)
VAT_BASIC = 0.01  # super-reduced (basic foods, books, health products)

VAT_RATES: dict[str, float] = {
    "standard": VAT_STANDARD,
    "reduced": VAT_REDUCED,
    "basic": VAT_BASIC,
    "exempt": 0.0,  # istisna / zero-rated (exports)
}

# ── Income tax (Gelir Vergisi) — progressive 2026 brackets, TRY ────────
# (upper_bound, marginal_rate). Final bracket bound is infinity.
INCOME_TAX_BRACKETS: list[tuple[float, float]] = [
    (190_000, 0.15),
    (400_000, 0.20),
    (1_000_000, 0.27),
    (5_300_000, 0.35),
    (float("inf"), 0.40),
]

# ── Corporate tax (Kurumlar Vergisi) 2026 ──────────────────────────────
CORPORATE_TAX_RATE = 0.25  # general rate (since Oct 2023)
CORPORATE_TAX_RATE_FINANCIAL = 0.30  # banks / insurers / petroleum
CORPORATE_TAX_RATE_EXPORTER = 0.20  # qualifying manufacturing exporters

# ── Stopaj (withholding) 2026 ──────────────────────────────────────────
STOPAJ_RATES: dict[str, float] = {
    "rent": 0.20,
    "freelancer": 0.17,
    "professional": 0.17,
}

# ── SGK (social security) rates 2026 ───────────────────────────────────
SGK_EMPLOYEE_RATE = 0.14  # 9% pension + 5% health
SGK_EMPLOYER_RATE = 0.195  # 12.5% pension + 7.5% health − 2pp treasury subsidy
UNEMPLOYMENT_EMPLOYEE_RATE = 0.01
UNEMPLOYMENT_EMPLOYER_RATE = 0.02

# ── Damga Vergisi (stamp tax) 2026 ─────────────────────────────────────
STAMP_PAYROLL_RATE = 0.00759  # 0.759% of gross salary (withheld by employer)
STAMP_CONTRACT_RATE = 0.00948  # 0.948% of contract value

StopajType = Literal["rent", "freelancer", "professional"]


# ── KDV / VAT ──────────────────────────────────────────────────────────
@dataclass
class KdvResult:
    net: float
    kdv: float
    total: float
    rate: float


def calc_kdv(amount: float, rate: float = VAT_STANDARD, inclusive: bool = False) -> KdvResult:
    """KDV breakdown for an amount.

    ``rate`` is a fraction (e.g. 0.20, 0.10, 0.01, or 0.0 for exempt).
    When ``inclusive`` the amount is the VAT-inclusive total; otherwise it is
    the net (pre-tax) amount.
    """
    if rate < 0:
        raise ValueError("KDV oranı negatif olamaz.")
    if inclusive:
        net = amount / (1 + rate)
        kdv = amount - net
        total = amount
    else:
        net = amount
        kdv = amount * rate
        total = amount + kdv
    return KdvResult(
        net=round(net, 2),
        kdv=round(kdv, 2),
        total=round(total, 2),
        rate=rate,
    )


def calc_vat(net_amount: float, rate_key: str = "standard") -> float:
    """VAT amount for a net (pre-tax) amount. Back-compat by rate key."""
    rate = VAT_RATES.get(rate_key, VAT_STANDARD)
    return round(net_amount * rate, 2)


def extract_vat_from_gross(gross_amount: float, rate_key: str = "standard") -> float:
    """Given a VAT-inclusive total, return the embedded VAT portion."""
    rate = VAT_RATES.get(rate_key, VAT_STANDARD)
    return round(gross_amount - gross_amount / (1 + rate), 2)


# ── Stopaj (withholding) ───────────────────────────────────────────────
@dataclass
class StopajResult:
    gross: float
    stopaj: float
    stamp: float
    net: float
    rate: float


def calc_stopaj(gross: float, stopaj_type: StopajType = "rent") -> StopajResult:
    """Net payable after withholding + stamp tax on a gross payment."""
    rate = STOPAJ_RATES.get(stopaj_type)
    if rate is None:
        raise ValueError(f"Bilinmeyen stopaj türü: {stopaj_type}")
    stopaj = gross * rate
    stamp = gross * STAMP_PAYROLL_RATE
    net = gross - stopaj - stamp
    return StopajResult(
        gross=round(gross, 2),
        stopaj=round(stopaj, 2),
        stamp=round(stamp, 2),
        net=round(net, 2),
        rate=rate,
    )


# ── Corporate tax (Kurumlar Vergisi) ───────────────────────────────────
@dataclass
class CorporateTaxResult:
    revenue: float
    expenses: float
    profit: float
    rate: float
    tax: float
    quarterly_payment: float


def calc_corporate_tax(
    revenue: float, expenses: float, rate: float = CORPORATE_TAX_RATE
) -> CorporateTaxResult:
    """Corporate tax on profit, with the quarterly provisional prepayment."""
    profit = revenue - expenses
    tax = max(profit, 0.0) * rate
    return CorporateTaxResult(
        revenue=round(revenue, 2),
        expenses=round(expenses, 2),
        profit=round(profit, 2),
        rate=rate,
        tax=round(tax, 2),
        quarterly_payment=round(tax / 4, 2),
    )


# ── Income tax (Gelir Vergisi) ─────────────────────────────────────────
def calc_income_tax(taxable_income: float) -> float:
    """Progressive income tax over the configured 2026 brackets."""
    tax = 0.0
    lower = 0.0
    for upper, rate in INCOME_TAX_BRACKETS:
        if taxable_income <= lower:
            break
        slice_amount = min(taxable_income, upper) - lower
        tax += slice_amount * rate
        lower = upper
    return round(tax, 2)


# ── SGK / full payroll ─────────────────────────────────────────────────
@dataclass
class SgkResult:
    gross_salary: float
    sgk_employee: float
    sgk_employer: float
    unemployment_employee: float
    unemployment_employer: float
    stamp_tax: float
    income_tax: float
    net_salary: float
    total_employer_cost: float


def calc_sgk(gross_salary: float) -> SgkResult:
    """Full monthly payroll breakdown from a gross salary.

    Income tax is applied to the SGK-reduced base (employee SGK + unemployment
    shares are deductible), annualised through the progressive brackets and
    brought back to a monthly figure — the correct Turkish method.
    """
    sgk_employee = gross_salary * SGK_EMPLOYEE_RATE
    sgk_employer = gross_salary * SGK_EMPLOYER_RATE
    unemployment_employee = gross_salary * UNEMPLOYMENT_EMPLOYEE_RATE
    unemployment_employer = gross_salary * UNEMPLOYMENT_EMPLOYER_RATE
    stamp_tax = gross_salary * STAMP_PAYROLL_RATE

    monthly_taxable = gross_salary - sgk_employee - unemployment_employee
    income_tax = calc_income_tax(monthly_taxable * 12) / 12

    net_salary = (
        gross_salary
        - sgk_employee
        - unemployment_employee
        - income_tax
        - stamp_tax
    )
    total_employer_cost = gross_salary + sgk_employer + unemployment_employer
    return SgkResult(
        gross_salary=round(gross_salary, 2),
        sgk_employee=round(sgk_employee, 2),
        sgk_employer=round(sgk_employer, 2),
        unemployment_employee=round(unemployment_employee, 2),
        unemployment_employer=round(unemployment_employer, 2),
        stamp_tax=round(stamp_tax, 2),
        income_tax=round(income_tax, 2),
        net_salary=round(net_salary, 2),
        total_employer_cost=round(total_employer_cost, 2),
    )


@dataclass
class PayslipResult:
    gross_salary: float
    sgk_deduction: float
    income_tax: float
    net_salary: float


def calc_payslip(base_salary: float, sgk_rate: float = SGK_EMPLOYEE_RATE) -> PayslipResult:
    """Net salary = gross − SGK employee share − income tax.

    Income tax is applied to the post-SGK base (SGK is deductible). Kept as a
    lightweight calculation for the employee list / payslip preview; the full
    breakdown lives in :func:`calc_sgk`.
    """
    gross = round(base_salary, 2)
    sgk = round(gross * sgk_rate, 2)
    taxable = gross - sgk
    tax = calc_income_tax(taxable)
    net = round(gross - sgk - tax, 2)
    return PayslipResult(
        gross_salary=gross,
        sgk_deduction=sgk,
        income_tax=tax,
        net_salary=net,
    )


# ── Reusable facade ────────────────────────────────────────────────────
class TaxEngine:
    """Stateless facade over the pure tax functions.

    Lets callers do ``TaxEngine.kdv(1000, 0.20)`` and get a plain ``dict``
    ready for JSON serialisation, without importing every function by name.
    """

    @staticmethod
    def kdv(amount: float, rate: float = VAT_STANDARD, inclusive: bool = False) -> dict:
        return asdict(calc_kdv(amount, rate, inclusive))

    @staticmethod
    def stopaj(gross: float, stopaj_type: StopajType = "rent") -> dict:
        return asdict(calc_stopaj(gross, stopaj_type))

    @staticmethod
    def corporate(
        revenue: float, expenses: float, rate: float = CORPORATE_TAX_RATE
    ) -> dict:
        return asdict(calc_corporate_tax(revenue, expenses, rate))

    @staticmethod
    def income(taxable_income: float) -> float:
        return calc_income_tax(taxable_income)

    @staticmethod
    def sgk(gross_salary: float) -> dict:
        return asdict(calc_sgk(gross_salary))

    @staticmethod
    def payslip(base_salary: float, sgk_rate: float = SGK_EMPLOYEE_RATE) -> dict:
        return asdict(calc_payslip(base_salary, sgk_rate))
