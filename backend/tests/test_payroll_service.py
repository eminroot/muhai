"""Payroll helpers — leave entitlement, overtime, severance."""
import pytest

from app.services.payroll_service import (
    annual_leave_entitlement,
    hourly_rate,
    tenure_years,
)
from datetime import date


@pytest.mark.parametrize(
    "years,expected",
    [(0.0, 0), (0.9, 0), (1.0, 14), (4.9, 14), (5.0, 20), (14.9, 20), (15.0, 26), (30.0, 26)],
)
def test_annual_leave_entitlement_bands(years, expected):
    assert annual_leave_entitlement(years) == expected


def test_hourly_rate_is_positive_and_proportional():
    assert hourly_rate(45_000) == pytest.approx(hourly_rate(22_500) * 2)
    assert hourly_rate(45_000) > 0


def test_tenure_years_counts_elapsed_time():
    assert tenure_years(date(2020, 1, 1), date(2026, 1, 1)) == pytest.approx(6.0, abs=0.05)


def test_tenure_years_handles_missing_start_date():
    assert tenure_years(None, date(2026, 1, 1)) == 0
