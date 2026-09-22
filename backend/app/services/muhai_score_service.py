"""Muhai Score — financial health score 0–100 (Module 12).

Pure, side-effect-free engine. The route layer aggregates business data into a
:class:`ScoreInputs` object; this module turns it into a weighted 0–100 score
plus an explainable breakdown (strengths, risks, recommendations).

Each category produces a sub-score in ``[0, 1]``; the total is the
weight-weighted sum scaled to 0–100. Where a business has no source data for a
category yet (e.g. no tax-payment history), that category resolves to a neutral
score rather than dragging the total down unfairly.
"""
from __future__ import annotations

from dataclasses import dataclass, field

# ── Category weights (must sum to 1.0) ─────────────────────────────────
WEIGHTS: dict[str, float] = {
    "tax_compliance": 0.15,
    "sgk_compliance": 0.10,
    "cash_flow": 0.20,
    "debt": 0.10,
    "invoice_collection": 0.15,
    "inventory": 0.05,
    "payroll_sustainability": 0.10,
    "profitability": 0.15,
}

# ── Turkish labels for display ─────────────────────────────────────────
LABELS: dict[str, str] = {
    "tax_compliance": "Vergi Uyumu",
    "sgk_compliance": "SGK Uyumu",
    "cash_flow": "Nakit Akışı",
    "debt": "Borç Yönetimi",
    "invoice_collection": "Tahsilat",
    "inventory": "Stok Yönetimi",
    "payroll_sustainability": "Bordro Sürdürülebilirliği",
    "profitability": "Kârlılık",
}

# Benchmarks
CASH_RUNWAY_TARGET_DAYS = 90.0
PAYROLL_HEALTHY_RATIO = 0.30
NET_MARGIN_BENCHMARK = 0.20


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def _ratio_on_time(total: int, on_time: int) -> float:
    """Compliance ratio. No obligations recorded → neutral (fully compliant)."""
    if total <= 0:
        return 1.0
    return _clamp(on_time / total)


@dataclass
class ScoreInputs:
    """Pre-aggregated business metrics feeding the score."""

    # Tax & SGK compliance (counts over the trailing 12 months)
    tax_deadlines_total: int = 0
    tax_deadlines_on_time: int = 0
    sgk_payments_total: int = 0
    sgk_payments_on_time: int = 0

    # Cash flow
    cash_balance: float = 0.0
    monthly_operating_expense: float = 0.0

    # Debt
    total_debt: float = 0.0
    total_assets: float = 0.0

    # Invoice collection
    invoices_total: int = 0
    invoices_collected_on_time: int = 0

    # Inventory
    inventory_items_total: int = 0
    inventory_items_healthy: int = 0

    # Payroll & profitability
    monthly_payroll: float = 0.0
    monthly_revenue: float = 0.0
    monthly_net_profit: float = 0.0


@dataclass
class CategoryScore:
    key: str
    label: str
    weight: float
    score: float  # 0..1
    points: float  # contribution to the 0..100 total (score * weight * 100)


@dataclass
class ScoreResult:
    total_score: int  # 0..100
    rating: str  # "red" | "yellow" | "green"
    cash_runway_days: float
    categories: list[CategoryScore] = field(default_factory=list)
    strengths: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)


# ── Per-category sub-scores (each returns 0..1) ────────────────────────
def _score_tax(m: ScoreInputs) -> float:
    return _ratio_on_time(m.tax_deadlines_total, m.tax_deadlines_on_time)


def _score_sgk(m: ScoreInputs) -> float:
    return _ratio_on_time(m.sgk_payments_total, m.sgk_payments_on_time)


def _cash_runway_days(m: ScoreInputs) -> float:
    daily_opex = m.monthly_operating_expense / 30.0
    if daily_opex <= 0:
        # No operating expenses: runway is effectively unbounded if solvent.
        return CASH_RUNWAY_TARGET_DAYS if m.cash_balance > 0 else 0.0
    return max(m.cash_balance, 0.0) / daily_opex


def _score_cash_flow(m: ScoreInputs) -> float:
    return _clamp(_cash_runway_days(m) / CASH_RUNWAY_TARGET_DAYS)


def _score_debt(m: ScoreInputs) -> float:
    if m.total_assets <= 0:
        return 1.0 if m.total_debt <= 0 else 0.0
    return _clamp(1.0 - (m.total_debt / m.total_assets))


def _score_invoice_collection(m: ScoreInputs) -> float:
    if m.invoices_total <= 0:
        return 1.0
    return _clamp(m.invoices_collected_on_time / m.invoices_total)


def _score_inventory(m: ScoreInputs) -> float:
    if m.inventory_items_total <= 0:
        return 1.0
    return _clamp(m.inventory_items_healthy / m.inventory_items_total)


def _score_payroll(m: ScoreInputs) -> float:
    if m.monthly_revenue <= 0:
        return 1.0 if m.monthly_payroll <= 0 else 0.0
    ratio = m.monthly_payroll / m.monthly_revenue
    if ratio <= PAYROLL_HEALTHY_RATIO:
        return 1.0
    # Degrade linearly; 0 once payroll reaches 2× the healthy share of revenue.
    return _clamp(1.0 - (ratio - PAYROLL_HEALTHY_RATIO) / PAYROLL_HEALTHY_RATIO)


def _score_profitability(m: ScoreInputs) -> float:
    if m.monthly_revenue <= 0:
        return 0.0
    net_margin = m.monthly_net_profit / m.monthly_revenue
    return _clamp(net_margin / NET_MARGIN_BENCHMARK)


_SCORERS = {
    "tax_compliance": _score_tax,
    "sgk_compliance": _score_sgk,
    "cash_flow": _score_cash_flow,
    "debt": _score_debt,
    "invoice_collection": _score_invoice_collection,
    "inventory": _score_inventory,
    "payroll_sustainability": _score_payroll,
    "profitability": _score_profitability,
}


# ── Narrative generation ───────────────────────────────────────────────
_RISK_ADVICE: dict[str, str] = {
    "tax_compliance": "Vergi beyannamelerini son güne bırakmayın; takvim hatırlatıcıları kurun.",
    "sgk_compliance": "SGK ödemelerini her ayın 23'ünden önce yapın, gecikme cezalarından kaçının.",
    "cash_flow": "Nakit rezervinizi güçlendirin: alacaklarınızı hızlandırın, gereksiz harcamaları erteleyin.",
    "debt": "Borç/varlık oranını düşürün; yüksek faizli borçları önceliklendirin.",
    "invoice_collection": "Vadesi geçen faturalar için tahsilat takibini sıkılaştırın.",
    "inventory": "Stok tükenme riski olan ürünler için zamanında yeniden sipariş verin.",
    "payroll_sustainability": "Bordro gideri ciroya göre yüksek; gelir artışı veya maliyet optimizasyonu değerlendirin.",
    "profitability": "Kâr marjınızı artırın: fiyatlandırmayı gözden geçirin veya maliyetleri düşürün.",
}

_STRENGTH_NOTE: dict[str, str] = {
    "tax_compliance": "Vergi yükümlülükleri zamanında yerine getiriliyor.",
    "sgk_compliance": "SGK ödemeleri düzenli ve zamanında.",
    "cash_flow": "Sağlıklı nakit rezervi mevcut.",
    "debt": "Borç seviyesi kontrol altında.",
    "invoice_collection": "Tahsilat performansı güçlü.",
    "inventory": "Stok seviyeleri sağlıklı.",
    "payroll_sustainability": "Bordro gideri ciroya göre sürdürülebilir.",
    "profitability": "Kârlılık hedeflerin üzerinde.",
}


def _generate_recommendations(ranked: list[CategoryScore]) -> list[str]:
    """Rule-based recommendations from the weakest categories (max 5).

    A Gemini-authored variant can be layered on later; this keeps the engine
    deterministic, offline-safe and unit-testable.
    """
    recs: list[str] = []
    for cat in ranked:
        if cat.score >= 0.85:
            continue
        advice = _RISK_ADVICE.get(cat.key)
        if advice:
            recs.append(advice)
        if len(recs) >= 5:
            break
    if not recs:
        recs.append("İşletmeniz güçlü durumda — mevcut disiplini koruyun.")
    return recs


def _rating(total: int) -> str:
    if total < 40:
        return "red"
    if total <= 70:
        return "yellow"
    return "green"


def compute_muhai_score(metrics: ScoreInputs) -> ScoreResult:
    """Compute the weighted Muhai Score and its explainable breakdown."""
    categories: list[CategoryScore] = []
    for key, weight in WEIGHTS.items():
        score = _clamp(_SCORERS[key](metrics))
        categories.append(
            CategoryScore(
                key=key,
                label=LABELS[key],
                weight=weight,
                score=round(score, 4),
                points=round(score * weight * 100, 2),
            )
        )

    total = round(sum(c.points for c in categories))
    total = int(_clamp(total, 0, 100))

    ranked_desc = sorted(categories, key=lambda c: c.score, reverse=True)
    ranked_asc = list(reversed(ranked_desc))

    strengths = [_STRENGTH_NOTE[c.key] for c in ranked_desc[:3] if c.score >= 0.6]
    risks = [_RISK_ADVICE[c.key] for c in ranked_asc[:3] if c.score < 0.85]

    return ScoreResult(
        total_score=total,
        rating=_rating(total),
        cash_runway_days=round(_cash_runway_days(metrics), 1),
        categories=categories,
        strengths=strengths,
        risks=risks,
        recommendations=_generate_recommendations(ranked_asc),
    )
