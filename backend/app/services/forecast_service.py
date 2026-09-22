"""Cash-flow forecasting service using Facebook Prophet.

Takes the last ~90 days of net daily cash flow and predicts the next 30 days.
Falls back to a simple moving-average projection when there is not enough data
for Prophet (which needs at least a couple of data points to be meaningful).
"""
from __future__ import annotations

import logging
from datetime import date, timedelta

from app.schemas.compute import ForecastPoint

logger = logging.getLogger(__name__)

FORECAST_HORIZON_DAYS = 30
MIN_POINTS_FOR_PROPHET = 10


def _moving_average_forecast(
    history: list[tuple[date, float]], horizon: int
) -> list[ForecastPoint]:
    """Fallback forecast: flat projection of the recent mean with a margin."""
    if not history:
        last_date = date.today()
        mean = 0.0
        margin = 0.0
    else:
        last_date = history[-1][0]
        values = [v for _, v in history]
        mean = sum(values) / len(values)
        # crude spread estimate for the confidence band
        margin = (max(values) - min(values)) / 2 or abs(mean) * 0.2

    points: list[ForecastPoint] = []
    for i in range(1, horizon + 1):
        d = last_date + timedelta(days=i)
        points.append(
            ForecastPoint(
                ds=d,
                yhat=round(mean, 2),
                yhat_lower=round(mean - margin, 2),
                yhat_upper=round(mean + margin, 2),
            )
        )
    return points


def forecast_cashflow(
    history: list[tuple[date, float]], horizon: int = FORECAST_HORIZON_DAYS
) -> list[ForecastPoint]:
    """Predict daily net cash flow for the next ``horizon`` days.

    Args:
        history: chronologically ordered (date, net_amount) pairs.
        horizon: number of future days to predict.
    """
    if len(history) < MIN_POINTS_FOR_PROPHET:
        return _moving_average_forecast(history, horizon)

    try:
        import pandas as pd
        from prophet import Prophet
    except ImportError:
        return _moving_average_forecast(history, horizon)

    # Anything Prophet raises degrades to the moving-average projection rather
    # than failing the request. A forecast is an advisory number: a coarser one
    # beats a 500. Logged at exception level so the cause is never silent.
    try:
        df = pd.DataFrame(history, columns=["ds", "y"])
        df["ds"] = pd.to_datetime(df["ds"])

        model = Prophet(
            daily_seasonality=False,
            weekly_seasonality=True,
            yearly_seasonality=False,
            interval_width=0.8,
        )
        model.fit(df)

        future = model.make_future_dataframe(periods=horizon)
        forecast = model.predict(future)

        tail = forecast.tail(horizon)
        return [
            ForecastPoint(
                ds=row["ds"].date(),
                yhat=round(float(row["yhat"]), 2),
                yhat_lower=round(float(row["yhat_lower"]), 2),
                yhat_upper=round(float(row["yhat_upper"]), 2),
            )
            for _, row in tail.iterrows()
        ]
    except Exception:
        logger.exception(
            "Prophet forecast failed; falling back to moving average. "
            "Check the cmdstanpy/prophet pairing in requirements.txt."
        )
        return _moving_average_forecast(history, horizon)
