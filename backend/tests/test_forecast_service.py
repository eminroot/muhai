"""Cash-flow forecasting — Prophet path and the small-sample fallback."""
from datetime import date, timedelta

import pytest

from app.services.forecast_service import (
    FORECAST_HORIZON_DAYS,
    MIN_POINTS_FOR_PROPHET,
    forecast_cashflow,
)


def _history(days: int, value: float = 1_000.0):
    start = date(2026, 1, 1)
    return [(start + timedelta(days=i), value + i) for i in range(days)]


def test_empty_history_still_returns_a_forecast():
    out = forecast_cashflow([], horizon=30)
    assert len(out) == 30


def test_short_history_uses_fallback_and_honours_horizon():
    out = forecast_cashflow(_history(MIN_POINTS_FOR_PROPHET - 1), horizon=15)
    assert len(out) == 15


def test_default_horizon_is_thirty_days():
    assert len(forecast_cashflow(_history(5))) == FORECAST_HORIZON_DAYS


def test_forecast_points_are_chronological_and_future():
    history = _history(5)
    last = history[-1][0]
    out = forecast_cashflow(history, horizon=10)
    dates = [p.ds for p in out]
    assert dates == sorted(dates)
    assert all(d > last for d in dates)


def test_confidence_band_brackets_the_prediction():
    for p in forecast_cashflow(_history(5), horizon=10):
        assert p.yhat_lower <= p.yhat <= p.yhat_upper


def test_prophet_path_returns_requested_horizon():
    """The real Prophet path, not the fallback.

    Regression guard for the cmdstanpy pin: prophet 1.1.5 ships a stripped
    cmdstan (no makefile) and cmdstanpy >= 1.3.0 rejects it, which made
    Prophet() raise and took every forecast with >= MIN_POINTS_FOR_PROPHET
    points down with it. requirements.txt pins cmdstanpy==1.2.4.
    """
    out = forecast_cashflow(_history(MIN_POINTS_FOR_PROPHET + 40), horizon=10)
    assert len(out) == 10
    for p in out:
        assert p.yhat_lower <= p.yhat <= p.yhat_upper


def test_prophet_backend_actually_loads():
    """Prophet must construct with a working Stan backend.

    Asserted directly so a bad cmdstanpy bump fails loudly here rather than
    silently degrading every forecast to the moving-average fallback.
    """
    from prophet import Prophet

    assert Prophet().stan_backend.get_type() == "CMDSTANPY"


def test_forecast_degrades_instead_of_raising(monkeypatch):
    """A broken Prophet must fall back, not 500."""
    import prophet

    class Exploding:
        def __init__(self, *a, **kw):
            raise RuntimeError("simulated stan backend failure")

    monkeypatch.setattr(prophet, "Prophet", Exploding)
    out = forecast_cashflow(_history(MIN_POINTS_FOR_PROPHET + 5), horizon=12)
    assert len(out) == 12
