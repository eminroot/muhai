"""Turkish tax-deadline calendar (Module 13 "Upcoming", seeds Module 10).

Pure functions: given a reference date, generate the upcoming statutory filing
deadlines. Monthly obligations recur on a fixed day; annual/quarterly ones fall
on fixed calendar dates. No DB, no side effects.

If a deadline lands on a non-business day the official date can shift; we keep
the nominal day here and leave business-day adjustment to a later refinement.
"""
from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date

# Monthly obligations: (type_key, Turkish name, day-of-month due, advance-warning days)
MONTHLY_OBLIGATIONS: list[tuple[str, str, int, int]] = [
    ("sgk", "SGK Primi", 23, 3),
    ("muhtasar", "Muhtasar (Stopaj)", 26, 5),
    ("damga", "Damga Vergisi", 26, 5),
    ("kdv", "KDV Beyannamesi", 28, 5),
]

# Fixed-date obligations: (type_key, Turkish name, month, day, advance-warning days)
ANNUAL_OBLIGATIONS: list[tuple[str, str, int, int, int]] = [
    ("gecici_vergi", "Geçici Vergi Q4", 2, 17, 7),
    ("gecici_vergi", "Geçici Vergi Q1", 5, 17, 7),
    ("gecici_vergi", "Geçici Vergi Q2", 8, 17, 7),
    ("gecici_vergi", "Geçici Vergi Q3", 11, 17, 7),
    ("kurumlar", "Kurumlar Vergisi Beyanı", 3, 31, 14),
    ("kurumlar", "Kurumlar Vergisi Ödemesi", 5, 31, 14),
    ("emlak", "Emlak Vergisi 1. Taksit", 5, 31, 7),
    ("emlak", "Emlak Vergisi 2. Taksit", 11, 30, 7),
    ("mtv", "MTV 1. Taksit", 2, 28, 14),
    ("mtv", "MTV 2. Taksit", 7, 31, 14),
]


@dataclass
class Deadline:
    type: str
    name: str
    due_date: date
    days_remaining: int
    advance_warning_days: int

    @property
    def is_due_soon(self) -> bool:
        return 0 <= self.days_remaining <= self.advance_warning_days


def _clamp_day(year: int, month: int, day: int) -> date:
    """Build a date, clamping the day to the month's last valid day."""
    last = calendar.monthrange(year, month)[1]
    return date(year, month, min(day, last))


def _next_monthly(today: date, due_day: int) -> date:
    """Next occurrence of a fixed day-of-month, today or later."""
    candidate = _clamp_day(today.year, today.month, due_day)
    if candidate >= today:
        return candidate
    month = today.month + 1
    year = today.year + (month - 1) // 12
    month = (month - 1) % 12 + 1
    return _clamp_day(year, month, due_day)


def _next_annual(today: date, month: int, day: int) -> date:
    """Next occurrence of a fixed calendar date, today or later."""
    candidate = _clamp_day(today.year, month, day)
    if candidate >= today:
        return candidate
    return _clamp_day(today.year + 1, month, day)


def upcoming_deadlines(today: date | None = None, count: int = 3) -> list[Deadline]:
    """Return the next ``count`` tax deadlines on or after ``today``."""
    today = today or date.today()

    items: list[Deadline] = []
    for type_key, name, due_day, warn in MONTHLY_OBLIGATIONS:
        due = _next_monthly(today, due_day)
        items.append(
            Deadline(type_key, name, due, (due - today).days, warn)
        )
    for type_key, name, month, day, warn in ANNUAL_OBLIGATIONS:
        due = _next_annual(today, month, day)
        items.append(
            Deadline(type_key, name, due, (due - today).days, warn)
        )

    items.sort(key=lambda d: d.due_date)
    return items[:count]
