"""Tax engine — the 2026 statutory formulas.

These are legal numbers, so the expected values here are computed by hand from
the published rates rather than captured from the implementation.
"""
import pytest

from app.services.tax_service import (
    CORPORATE_TAX_RATE,
    SGK_EMPLOYEE_RATE,
    VAT_STANDARD,
    TaxEngine,
    calc_corporate_tax,
    calc_income_tax,
    calc_kdv,
    calc_payslip,
    calc_sgk,
    calc_stopaj,
    calc_vat,
    extract_vat_from_gross,
)


# ── KDV ────────────────────────────────────────────────────────────────
def test_kdv_exclusive_adds_tax_on_top():
    r = calc_kdv(1000, VAT_STANDARD)
    assert (r.net, r.kdv, r.total) == (1000.00, 200.00, 1200.00)


def test_kdv_inclusive_extracts_embedded_tax():
    r = calc_kdv(1200, VAT_STANDARD, inclusive=True)
    assert (r.net, r.kdv, r.total) == (1000.00, 200.00, 1200.00)


def test_kdv_exempt_rate_is_zero():
    r = calc_kdv(1000, 0.0)
    assert r.kdv == 0.0 and r.total == 1000.00


def test_kdv_rejects_negative_rate():
    with pytest.raises(ValueError):
        calc_kdv(1000, -0.20)


def test_kdv_inclusive_and_exclusive_are_inverse():
    gross = calc_kdv(2500, VAT_STANDARD).total
    assert calc_kdv(gross, VAT_STANDARD, inclusive=True).net == 2500.00


def test_calc_vat_by_rate_key():
    assert calc_vat(1000, "standard") == 200.00
    assert calc_vat(1000, "reduced") == 100.00
    assert calc_vat(1000, "basic") == 10.00
    assert calc_vat(1000, "exempt") == 0.00


def test_calc_vat_unknown_key_falls_back_to_standard():
    assert calc_vat(1000, "nonsense") == 200.00


def test_extract_vat_from_gross():
    assert extract_vat_from_gross(1200, "standard") == 200.00


# ── Gelir vergisi (progressive brackets) ───────────────────────────────
def test_income_tax_zero_income():
    assert calc_income_tax(0) == 0.0


def test_income_tax_within_first_bracket():
    # 100.000 * 15%
    assert calc_income_tax(100_000) == 15_000.00


def test_income_tax_spans_two_brackets():
    # 190.000*15% = 28.500  +  110.000*20% = 22.000
    assert calc_income_tax(300_000) == 50_500.00


def test_income_tax_spans_three_brackets():
    # 28.500 + 42.000 + (510.000-400.000)*27% = 29.700
    assert calc_income_tax(510_000) == 100_200.00


def test_income_tax_is_monotonic():
    values = [calc_income_tax(x) for x in (0, 50_000, 190_000, 400_000, 1_000_000)]
    assert values == sorted(values)


# ── Stopaj ─────────────────────────────────────────────────────────────
def test_stopaj_rent_withholding_and_stamp():
    r = calc_stopaj(10_000, "rent")
    assert r.stopaj == 2_000.00          # 20%
    assert r.stamp == 75.90              # 0.759%
    assert r.net == 7_924.10


def test_stopaj_freelancer_rate():
    assert calc_stopaj(10_000, "freelancer").stopaj == 1_700.00


def test_stopaj_rejects_unknown_type():
    with pytest.raises(ValueError):
        calc_stopaj(10_000, "unknown")


# ── Kurumlar vergisi ───────────────────────────────────────────────────
def test_corporate_tax_on_profit():
    r = calc_corporate_tax(1_000_000, 400_000, CORPORATE_TAX_RATE)
    assert r.profit == 600_000.00
    assert r.tax == 150_000.00           # 25%
    assert r.quarterly_payment == 37_500.00


def test_corporate_tax_on_loss_is_zero():
    r = calc_corporate_tax(200_000, 500_000)
    assert r.profit == -300_000.00
    assert r.tax == 0.0


# ── SGK / full payroll ─────────────────────────────────────────────────
def test_sgk_full_breakdown_for_50k_gross():
    r = calc_sgk(50_000)
    assert r.sgk_employee == 7_000.00            # 14%
    assert r.sgk_employer == 9_750.00            # 19.5%
    assert r.unemployment_employee == 500.00     # 1%
    assert r.unemployment_employer == 1_000.00   # 2%
    assert r.stamp_tax == 379.50                 # 0.759%
    # taxable 42.500/mo -> 510.000/yr -> 100.200 tax -> 8.350/mo
    assert r.income_tax == 8_350.00
    assert r.net_salary == 33_770.50
    assert r.total_employer_cost == 60_750.00


def test_employer_cost_always_exceeds_gross():
    r = calc_sgk(30_000)
    assert r.total_employer_cost > r.gross_salary


def test_net_salary_never_exceeds_gross():
    for gross in (15_000, 50_000, 250_000):
        assert calc_sgk(gross).net_salary < gross


# ── Payslip (lightweight) ──────────────────────────────────────────────
def test_payslip_deducts_sgk_then_income_tax():
    r = calc_payslip(50_000, SGK_EMPLOYEE_RATE)
    assert r.sgk_deduction == 7_000.00
    assert r.income_tax == calc_income_tax(43_000)
    assert r.net_salary == round(50_000 - 7_000 - r.income_tax, 2)


# ── Facade ─────────────────────────────────────────────────────────────
def test_tax_engine_returns_serialisable_dicts():
    assert TaxEngine.kdv(1000)["kdv"] == 200.00
    assert TaxEngine.corporate(1_000_000, 400_000)["tax"] == 150_000.00
    assert TaxEngine.income(100_000) == 15_000.00
    assert TaxEngine.sgk(50_000)["sgk_employee"] == 7_000.00
    assert TaxEngine.payslip(50_000)["sgk_deduction"] == 7_000.00
    assert TaxEngine.stopaj(10_000, "rent")["stopaj"] == 2_000.00
