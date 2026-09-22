"""Muhai Score — weighted 0-100 financial health engine."""
from app.services.muhai_score_service import (
    LABELS,
    WEIGHTS,
    ScoreInputs,
    compute_muhai_score,
)


def _healthy() -> ScoreInputs:
    return ScoreInputs(
        tax_deadlines_total=12,
        tax_deadlines_on_time=12,
        sgk_payments_total=12,
        sgk_payments_on_time=12,
        cash_balance=300_000,
        monthly_operating_expense=100_000,
        monthly_payroll=25_000,
        monthly_revenue=250_000,
        monthly_net_profit=60_000,
    )


def test_weights_sum_to_one():
    assert round(sum(WEIGHTS.values()), 6) == 1.0


def test_every_weight_has_a_turkish_label():
    assert set(WEIGHTS) == set(LABELS)


def test_score_is_within_bounds():
    for metrics in (ScoreInputs(), _healthy()):
        assert 0 <= compute_muhai_score(metrics).total_score <= 100


def test_rating_is_a_known_band():
    assert compute_muhai_score(_healthy()).rating in {"red", "yellow", "green"}


def test_category_points_reconcile_with_total():
    result = compute_muhai_score(_healthy())
    assert round(sum(c.points for c in result.categories)) == result.total_score


def test_every_category_is_reported():
    result = compute_muhai_score(_healthy())
    assert {c.key for c in result.categories} == set(WEIGHTS)


def test_each_subscore_is_normalised():
    for c in compute_muhai_score(_healthy()).categories:
        assert 0.0 <= c.score <= 1.0


def test_healthy_business_outscores_distressed_one():
    distressed = ScoreInputs(
        tax_deadlines_total=12,
        tax_deadlines_on_time=3,
        sgk_payments_total=12,
        sgk_payments_on_time=4,
        cash_balance=5_000,
        monthly_operating_expense=120_000,
        monthly_payroll=90_000,
        monthly_revenue=100_000,
        monthly_net_profit=-20_000,
    )
    assert compute_muhai_score(_healthy()).total_score > compute_muhai_score(distressed).total_score


def test_cash_runway_reflects_balance_over_burn():
    # 300.000 balance / 100.000 monthly burn -> roughly 90 days
    result = compute_muhai_score(_healthy())
    assert 80 <= result.cash_runway_days <= 100


def test_empty_inputs_do_not_raise():
    result = compute_muhai_score(ScoreInputs())
    assert isinstance(result.total_score, int)
    assert isinstance(result.recommendations, list)
