"""Detailed payroll engine (Module 4 — Payroll & SGK).

Pure, side-effect-free. Builds on the Module 2 tax engine (`tax_service`) to
produce a full monthly payslip: overtime, meal/transport allowances (with their
tax-exempt portions), bonus, every statutory deduction, employer cost, plus a
severance estimate and annual-leave accrual.

Statutory rates come from `tax_service` (single source of truth). The
allowance exemption limits are 2026 *defaults* exposed as parameters — override
them per the current official figures rather than treating them as frozen law.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from app.services.tax_service import (
    SGK_EMPLOYEE_RATE,
    SGK_EMPLOYER_RATE,
    STAMP_PAYROLL_RATE,
    UNEMPLOYMENT_EMPLOYEE_RATE,
    UNEMPLOYMENT_EMPLOYER_RATE,
    calc_income_tax,
)

# Legal monthly working hours used to derive an hourly rate (30 days × 7.5h).
MONTHLY_WORK_HOURS = 225.0
OVERTIME_WEEKDAY_MULTIPLIER = 1.5
OVERTIME_WEEKEND_MULTIPLIER = 2.0

# Allowance tax-exempt limits — 2026 defaults (configurable, override as needed).
DEFAULT_MEAL_EXEMPT_DAILY = 240.0  # per worked day, KDV hariç
DEFAULT_TRANSPORT_EXEMPT_DAILY = 126.0  # per worked day

# Annual leave entitlement by tenure (Turkish Labour Law art. 53), days/year.
def annual_leave_entitlement(tenure_years: float) -> int:
    if tenure_years < 1:
        return 0
    if tenure_years < 5:
        return 14
    if tenure_years < 15:
        return 20
    return 26


def hourly_rate(gross_salary: float) -> float:
    return gross_salary / MONTHLY_WORK_HOURS


def calc_overtime_pay(
    gross_salary: float, weekday_hours: float = 0.0, weekend_hours: float = 0.0
) -> float:
    rate = hourly_rate(gross_salary)
    pay = (
        weekday_hours * rate * OVERTIME_WEEKDAY_MULTIPLIER
        + weekend_hours * rate * OVERTIME_WEEKEND_MULTIPLIER
    )
    return round(pay, 2)


def _exempt_split(paid: float, exempt_limit: float) -> tuple[float, float]:
    """Return (exempt_portion, taxable_excess) for an allowance."""
    exempt = min(paid, exempt_limit)
    return round(exempt, 2), round(max(paid - exempt_limit, 0.0), 2)


def tenure_years(start: date | None, as_of: date | None = None) -> float:
    if start is None:
        return 0.0
    as_of = as_of or date.today()
    return max((as_of - start).days / 365.0, 0.0)


def calc_severance(gross_salary: float, start: date | None, as_of: date | None = None) -> float:
    """Kıdem tazminatı estimate: 30 days' gross per full year, if tenure ≥ 1y.

    (Statutory ceiling not applied — this is an estimate.)
    """
    years = tenure_years(start, as_of)
    if years < 1:
        return 0.0
    return round(gross_salary * years, 2)


@dataclass
class DetailedPayslip:
    # Earnings
    gross_salary: float
    overtime_pay: float
    bonus: float
    meal_allowance: float
    transport_allowance: float
    total_earnings: float
    # Tax-exempt allowance portions (informational)
    meal_exempt: float
    transport_exempt: float
    taxable_base: float  # SGK / income-tax base
    # Deductions
    sgk_employee: float
    unemployment_employee: float
    income_tax: float
    stamp_tax: float
    total_deductions: float
    # Results
    net_salary: float
    sgk_employer: float
    unemployment_employer: float
    total_employer_cost: float
    # Tenure-derived
    tenure_years: float
    severance_estimate: float
    annual_leave_days: int


def calc_detailed_payslip(
    gross_salary: float,
    *,
    overtime_weekday_hours: float = 0.0,
    overtime_weekend_hours: float = 0.0,
    bonus: float = 0.0,
    meal_allowance: float = 0.0,
    transport_allowance: float = 0.0,
    worked_days: int = 30,
    start_date: date | None = None,
    as_of: date | None = None,
    meal_exempt_daily: float = DEFAULT_MEAL_EXEMPT_DAILY,
    transport_exempt_daily: float = DEFAULT_TRANSPORT_EXEMPT_DAILY,
) -> DetailedPayslip:
    overtime_pay = calc_overtime_pay(
        gross_salary, overtime_weekday_hours, overtime_weekend_hours
    )

    meal_exempt, meal_excess = _exempt_split(meal_allowance, meal_exempt_daily * worked_days)
    transport_exempt, transport_excess = _exempt_split(
        transport_allowance, transport_exempt_daily * worked_days
    )

    # SGK & income tax base: cash earnings + only the taxable allowance excess.
    taxable_base = round(
        gross_salary + overtime_pay + bonus + meal_excess + transport_excess, 2
    )

    sgk_employee = round(taxable_base * SGK_EMPLOYEE_RATE, 2)
    sgk_employer = round(taxable_base * SGK_EMPLOYER_RATE, 2)
    unemployment_employee = round(taxable_base * UNEMPLOYMENT_EMPLOYEE_RATE, 2)
    unemployment_employer = round(taxable_base * UNEMPLOYMENT_EMPLOYER_RATE, 2)
    stamp_tax = round(taxable_base * STAMP_PAYROLL_RATE, 2)

    income_taxable = taxable_base - sgk_employee - unemployment_employee
    income_tax = round(calc_income_tax(income_taxable * 12) / 12, 2)

    total_earnings = round(
        gross_salary + overtime_pay + bonus + meal_allowance + transport_allowance, 2
    )
    total_deductions = round(
        sgk_employee + unemployment_employee + income_tax + stamp_tax, 2
    )
    net_salary = round(total_earnings - total_deductions, 2)
    total_employer_cost = round(total_earnings + sgk_employer + unemployment_employer, 2)

    years = tenure_years(start_date, as_of)

    return DetailedPayslip(
        gross_salary=round(gross_salary, 2),
        overtime_pay=overtime_pay,
        bonus=round(bonus, 2),
        meal_allowance=round(meal_allowance, 2),
        transport_allowance=round(transport_allowance, 2),
        total_earnings=total_earnings,
        meal_exempt=meal_exempt,
        transport_exempt=transport_exempt,
        taxable_base=taxable_base,
        sgk_employee=sgk_employee,
        unemployment_employee=unemployment_employee,
        income_tax=income_tax,
        stamp_tax=stamp_tax,
        total_deductions=total_deductions,
        net_salary=net_salary,
        sgk_employer=sgk_employer,
        unemployment_employer=unemployment_employer,
        total_employer_cost=total_employer_cost,
        tenure_years=round(years, 2),
        severance_estimate=calc_severance(gross_salary, start_date, as_of),
        annual_leave_days=annual_leave_entitlement(years),
    )
