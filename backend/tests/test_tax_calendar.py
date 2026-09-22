"""Statutory filing calendar generation."""
from datetime import date

from app.services.tax_calendar import (
    ANNUAL_OBLIGATIONS,
    MONTHLY_OBLIGATIONS,
    upcoming_deadlines,
)

TODAY = date(2026, 6, 1)


def test_returns_requested_count():
    assert len(upcoming_deadlines(TODAY, count=3)) == 3
    assert len(upcoming_deadlines(TODAY, count=7)) == 7


def test_deadlines_are_in_the_future():
    for d in upcoming_deadlines(TODAY, count=10):
        assert d.due_date >= TODAY


def test_deadlines_are_chronologically_sorted():
    dates = [d.due_date for d in upcoming_deadlines(TODAY, count=10)]
    assert dates == sorted(dates)


def test_days_remaining_matches_due_date():
    for d in upcoming_deadlines(TODAY, count=5):
        assert d.days_remaining == (d.due_date - TODAY).days


def test_known_obligation_types_only():
    known = {o[0] for o in MONTHLY_OBLIGATIONS} | {o[0] for o in ANNUAL_OBLIGATIONS}
    for d in upcoming_deadlines(TODAY, count=12):
        assert d.type in known


def test_monthly_kdv_appears_within_the_month():
    # KDV is due on the 28th, so from 1 June it must show up in the next few.
    kinds = [d.type for d in upcoming_deadlines(TODAY, count=6)]
    assert "kdv" in kinds


def test_defaults_to_today_when_no_date_given():
    assert len(upcoming_deadlines()) == 3


def test_year_end_rollover_does_not_break():
    for d in upcoming_deadlines(date(2026, 12, 30), count=6):
        assert d.due_date >= date(2026, 12, 30)
