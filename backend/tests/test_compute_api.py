"""Tests for the stateless /api/compute layer.

This is the surface the web client actually calls, so it is covered end to end
through the FastAPI app — no database, no network call. Auth is
disabled per-test by flipping ``COMPUTE_AUTH_REQUIRED``; a separate test
asserts that the flag genuinely gates the endpoints.
"""
import datetime as dt

import pytest

from app.core.config import settings


AS_OF = dt.date(2026, 6, 30)


@pytest.fixture(autouse=True)
def open_auth():
    """Run the compute endpoints unauthenticated, restoring the setting after."""
    original = settings.COMPUTE_AUTH_REQUIRED
    settings.COMPUTE_AUTH_REQUIRED = False
    yield
    settings.COMPUTE_AUTH_REQUIRED = original


def _transactions(months: int = 12, day_step: int = 3) -> list[dict]:
    """A dense, deterministic 12-month history with a mild upward trend."""
    txs = []
    for m in range(months):
        month = AS_OF.month - m
        year = AS_OF.year
        while month <= 0:
            month += 12
            year -= 1
        for day in range(1, 29, day_step):
            txs.append(
                {
                    "date": dt.date(year, month, day).isoformat(),
                    "amount": 12_000 + (months - m) * 250,
                    "type": "income",
                    "category": "sales",
                }
            )
            txs.append(
                {
                    "date": dt.date(year, month, day).isoformat(),
                    "amount": 7_000 + (months - m) * 100,
                    "type": "expense",
                    "category": "raw_materials",
                }
            )
    return txs


def _snapshot(**overrides) -> dict:
    base = {
        "as_of": AS_OF.isoformat(),
        "cash_balance": 250_000,
        "transactions": _transactions(),
        "invoices": [
            {
                "date": "2026-06-01",
                "due_date": "2026-06-15",
                "amount": 14_820,
                "vat_amount": 2_470,
                "vendor": "Anadolu Tedarik A.Ş.",
                "status": "pending",
                "direction": "sales",
            },
            {
                "date": "2026-05-02",
                "due_date": "2026-05-16",
                "paid_date": "2026-05-14",
                "amount": 9_230,
                "vendor": "Ege Ambalaj Ltd.",
                "status": "paid",
                "direction": "sales",
            },
        ],
        "products": [
            {"name": "A4 Kağıt", "stock": 120, "min_stock": 40, "unit_price": 185},
            {"name": "Toner", "stock": 3, "min_stock": 10, "unit_price": 420},
        ],
        "employees": [
            {"name": "Emin B.", "gross_salary": 45_000, "start_date": "2022-03-01"},
            {"name": "Selin K.", "gross_salary": 38_000, "start_date": "2024-09-15"},
        ],
    }
    base.update(overrides)
    return base


# ── Wiring ─────────────────────────────────────────────────────────────
def test_compute_routes_are_mounted(client):
    paths = client.get("/openapi.json").json()["paths"]
    for expected in (
        "/api/compute/dashboard",
        "/api/compute/muhai-score",
        "/api/compute/forecast",
        "/api/compute/tax-summary",
        "/api/compute/payroll",
        "/api/compute/classify",
        "/api/compute/compliance",
        "/api/compute/ocr",
        "/api/compute/chat",
    ):
        assert expected in paths, f"{expected} is not mounted"


def test_auth_is_enforced_when_required(client):
    settings.COMPUTE_AUTH_REQUIRED = True
    r = client.post("/api/compute/dashboard", json=_snapshot())
    assert r.status_code == 401


# ── Dashboard ──────────────────────────────────────────────────────────
def test_dashboard_returns_twelve_gapless_months(client):
    body = client.post("/api/compute/dashboard", json=_snapshot()).json()
    months = body["monthly"]
    assert len(months) == 12
    assert months[-1]["month"] == "2026-06"
    assert months[0]["month"] == "2025-07"
    # Every month must be present even with no movement — charts need no gaps.
    assert all("income" in m and "expense" in m for m in months)


def test_dashboard_kpis_match_the_latest_month(client):
    body = client.post("/api/compute/dashboard", json=_snapshot()).json()
    latest = body["monthly"][-1]
    assert body["kpis"]["revenue"] == latest["income"]
    assert body["kpis"]["expense"] == latest["expense"]
    assert body["kpis"]["profit"] == pytest.approx(latest["income"] - latest["expense"])


def test_dashboard_splits_receivables_from_payables(client):
    body = client.post("/api/compute/dashboard", json=_snapshot()).json()
    assert body["receivables"] == 14_820
    assert body["payables"] == 0
    assert body["overdue_count"] == 1  # pending, due 15 Jun, as_of 30 Jun


def test_dashboard_survives_an_empty_company(client):
    body = client.post(
        "/api/compute/dashboard",
        json={"as_of": AS_OF.isoformat(), "transactions": [], "invoices": []},
    ).json()
    assert body["kpis"]["revenue"] == 0
    assert len(body["monthly"]) == 12
    assert body["insight"]


def test_uncategorised_expenses_are_classified_not_dropped(client):
    snap = _snapshot(
        transactions=[
            {
                "date": "2026-06-10",
                "amount": 5_000,
                "type": "expense",
                "description": "Klima bakim ve onarim",
            }
        ]
    )
    breakdown = client.post("/api/compute/dashboard", json=snap).json()["expense_breakdown"]
    assert {b["key"] for b in breakdown} == {"maintenance"}
    assert breakdown[0]["value"] == 5_000


# ── Compliance ─────────────────────────────────────────────────────────
def _alerts(client, **overrides) -> list[dict]:
    return client.post("/api/compute/compliance", json=_snapshot(**overrides)).json()["alerts"]


def _invoice_alerts(alerts: list[dict]) -> list[dict]:
    """Everything except the deadline warnings, which depend on the calendar."""
    return [a for a in alerts if a["type"] != "tax_deadline"]


def test_clean_invoices_raise_no_invoice_alerts(client):
    # The fixture's KDV is exactly 20% of net and no document repeats, so any
    # invoice-level alert here would be a false positive.
    assert _invoice_alerts(_alerts(client)) == []


def test_a_repeated_invoice_number_is_flagged_high(client):
    dupe = {
        "id": "inv-1",
        "number": "MUH-2026-0001",
        "date": "2026-06-01",
        "amount": 14_820,
        "vat_amount": 2_470,
        "vendor": "Anadolu Tedarik A.Ş.",
    }
    alerts = _invoice_alerts(
        _alerts(client, invoices=[dupe, {**dupe, "id": "inv-2", "date": "2026-06-04"}])
    )
    assert len(alerts) == 1
    assert alerts[0]["type"] == "duplicate_invoice"
    assert alerts[0]["severity"] == "high"
    assert alerts[0]["ref_id"] == "inv-1"
    assert "MUH-2026-0001" in alerts[0]["description"]


def test_same_amount_date_and_vendor_is_flagged_without_a_number(client):
    twin = {
        "id": "inv-1",
        "date": "2026-06-01",
        "amount": 6_000,   # 1.000 KDV on 5.000 net — a clean 20%
        "vat_amount": 1_000,
        "vendor": "Ege Ambalaj Ltd.",
    }
    alerts = _invoice_alerts(_alerts(client, invoices=[twin, {**twin, "id": "inv-2"}]))
    assert [a["type"] for a in alerts] == ["duplicate_invoice"]
    assert alerts[0]["severity"] == "medium"


def test_kdv_larger_than_the_total_is_flagged_high(client):
    alerts = _invoice_alerts(
        _alerts(
            client,
            invoices=[{"id": "inv-1", "date": "2026-06-01", "amount": 1_000, "vat_amount": 1_400}],
        )
    )
    assert [(a["type"], a["severity"]) for a in alerts] == [("suspicious_invoice", "high")]
    assert alerts[0]["ref_id"] == "inv-1"


def test_a_kdv_rate_that_is_not_legal_is_flagged(client):
    # 137 / 863 ≈ 15.9% — not 1, 10 or 20 (nor the historical 8/18).
    alerts = _invoice_alerts(
        _alerts(
            client,
            invoices=[{"id": "inv-1", "date": "2026-06-01", "amount": 1_000, "vat_amount": 137}],
        )
    )
    assert [(a["type"], a["severity"]) for a in alerts] == [("suspicious_invoice", "medium")]


def test_zero_kdv_is_treated_as_exempt_not_suspicious(client):
    alerts = _invoice_alerts(
        _alerts(
            client,
            invoices=[{"id": "inv-1", "date": "2026-06-01", "amount": 1_000, "vat_amount": 0}],
        )
    )
    assert alerts == []


def test_alerts_are_severity_ordered_and_counted(client):
    body = client.post(
        "/api/compute/compliance",
        json=_snapshot(
            invoices=[
                {"id": "a", "number": "X-1", "date": "2026-06-01", "amount": 1_000, "vat_amount": 200},
                {"id": "b", "number": "X-1", "date": "2026-06-02", "amount": 2_000, "vat_amount": 400},
                {"id": "c", "date": "2026-06-03", "amount": 1_000, "vat_amount": 137},
            ]
        ),
    ).json()

    severities = [a["severity"] for a in body["alerts"]]
    rank = {"high": 0, "medium": 1, "low": 2}
    assert severities == sorted(severities, key=lambda s: rank[s])

    assert body["total"] == len(body["alerts"])
    assert body["high"] == severities.count("high")
    assert body["medium"] == severities.count("medium")
    assert body["low"] == severities.count("low")


def test_deadline_alerts_carry_no_invoice_reference(client):
    alerts = client.post("/api/compute/compliance", json=_snapshot()).json()["alerts"]
    for a in alerts:
        if a["type"] == "tax_deadline":
            assert a["ref_id"] is None
            assert a["description"]


def test_compliance_survives_an_empty_company(client):
    body = client.post(
        "/api/compute/compliance",
        json={"as_of": AS_OF.isoformat(), "invoices": []},
    ).json()
    assert _invoice_alerts(body["alerts"]) == []
    assert body["total"] == len(body["alerts"])


# ── Muhai Score ────────────────────────────────────────────────────────
def test_muhai_score_is_bounded_and_explained(client):
    body = client.post("/api/compute/muhai-score", json=_snapshot()).json()
    assert 0 <= body["total_score"] <= 100
    assert body["rating"] in {"red", "yellow", "green"}
    assert len(body["categories"]) == 8
    assert sum(c["weight"] for c in body["categories"]) == pytest.approx(1.0)
    assert body["cash_runway_days"] >= 0


# ── Forecast ───────────────────────────────────────────────────────────
def test_forecast_uses_prophet_on_a_dense_history(client):
    body = client.post("/api/compute/forecast?horizon=30", json=_snapshot()).json()
    assert body["engine"] == "prophet"
    assert len(body["points"]) == 30
    for p in body["points"]:
        assert p["yhat_lower"] <= p["yhat"] <= p["yhat_upper"]


def test_forecast_horizon_is_clamped(client):
    body = client.post("/api/compute/forecast?horizon=9999", json=_snapshot()).json()
    assert body["horizon_days"] == 180
    assert len(body["points"]) == 180


# ── Tax ────────────────────────────────────────────────────────────────
def test_tax_summary_nets_kdv_and_never_goes_negative(client):
    body = client.post("/api/compute/tax-summary", json=_snapshot()).json()
    assert body["kdv_payable"] == pytest.approx(
        max(body["kdv_collected"] - body["kdv_paid"], 0), abs=0.01
    )
    assert body["kdv_payable"] >= 0
    assert body["period"] == "2026-06"
    assert len(body["deadlines"]) == 6


def test_corporate_tax_is_assessed_on_the_trailing_year(client):
    body = client.post("/api/compute/tax-summary", json=_snapshot()).json()
    dash = client.post("/api/compute/dashboard", json=_snapshot()).json()
    assert body["revenue"] == pytest.approx(
        sum(m["income"] for m in dash["monthly"]), abs=0.01
    )
    assert body["corporate_quarterly"] == pytest.approx(body["corporate_tax"] / 4, abs=0.01)


# ── Payroll ────────────────────────────────────────────────────────────
def test_payroll_run_totals_match_the_payslips(client):
    body = client.post("/api/compute/payroll", json=_snapshot()).json()
    assert body["headcount"] == 2
    assert body["total_gross"] == pytest.approx(83_000)
    assert body["total_net"] == pytest.approx(
        sum(p["net_salary"] for p in body["payslips"]), abs=0.01
    )
    for slip in body["payslips"]:
        assert slip["net_salary"] < slip["gross_salary"]
        assert slip["total_employer_cost"] > slip["gross_salary"]


# ── Classification ─────────────────────────────────────────────────────
def test_classify_batch_preserves_ids(client):
    payload = {
        "items": [
            {"id": "a", "description": "Shell akaryakit"},
            {"id": "b", "description": "Google reklam"},
            {"id": "c", "description": "zzzz"},
        ]
    }
    body = client.post("/api/compute/classify", json=payload).json()
    assert [i["id"] for i in body["items"]] == ["a", "b", "c"]
    assert [i["category"] for i in body["items"]] == ["fuel", "marketing", "other"]
    assert {i["source"] for i in body["items"]} == {"rules"}


def test_a_learned_vendor_beats_the_keyword_rules(client):
    # "Teknopark" hits no rule, so the rules alone would say "other".
    payload = {
        "items": [{"id": "a", "vendor": "Teknopark Gayrimenkul A.Ş."}],
        "learned": {"teknopark gayrimenkul as": "rent"},
    }
    body = client.post("/api/compute/classify", json=payload).json()
    assert body["items"][0] == {"id": "a", "category": "rent", "source": "learned"}


def test_a_learned_vendor_overrides_a_confident_rule(client):
    # "Shell" is a fuel keyword. If this company files Shell under travel,
    # its own correction has to win — that is the whole point of learning.
    payload = {
        "items": [{"id": "a", "vendor": "Shell", "description": "Shell akaryakit"}],
        "learned": {"shell": "travel"},
    }
    body = client.post("/api/compute/classify", json=payload).json()
    assert body["items"][0]["category"] == "travel"
    assert body["items"][0]["source"] == "learned"


@pytest.mark.parametrize(
    "written",
    [
        "Teknopark Gayrimenkul A.Ş.",
        "teknopark gayrimenkul as",
        "  TEKNOPARK   Gayrimenkul  AŞ  ",
        "Teknopark Gayrımenkul A.S.",
    ],
)
def test_vendor_spelling_variants_hit_the_same_learned_entry(client, written):
    """Punctuation, case, spacing and Turkish diacritics must not split a vendor."""
    body = client.post(
        "/api/compute/classify",
        json={
            "items": [{"id": "a", "vendor": written}],
            "learned": {"Teknopark Gayrimenkul A.Ş.": "rent"},
        },
    ).json()
    assert body["items"][0]["category"] == "rent"


def test_an_unknown_category_in_the_learned_map_is_ignored(client):
    """A corrupted or hand-edited map must not inject a category the UI cannot render."""
    body = client.post(
        "/api/compute/classify",
        json={
            "items": [{"id": "a", "vendor": "Shell", "description": "Shell akaryakit"}],
            "learned": {"shell": "not_a_real_category"},
        },
    ).json()
    assert body["items"][0]["category"] == "fuel"
    assert body["items"][0]["source"] == "rules"


def test_classify_without_a_learned_map_still_works(client):
    """The field is optional: an older client posts only `items`."""
    body = client.post(
        "/api/compute/classify",
        json={"items": [{"id": "a", "description": "Shell akaryakit"}]},
    ).json()
    assert body["items"][0]["category"] == "fuel"


# ── Chat ───────────────────────────────────────────────────────────────
def test_chat_grounds_on_the_snapshot(client):
    r = client.post(
        "/api/compute/chat",
        json={"message": "Nakit durumum nasıl?", "snapshot": _snapshot()},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["reply"]
    assert body["source"] in {"placeholder", "ai", "offline"}


def test_chat_works_without_a_snapshot(client):
    r = client.post("/api/compute/chat", json={"message": "KDV nedir?"})
    assert r.status_code == 200
    assert r.json()["reply"]
