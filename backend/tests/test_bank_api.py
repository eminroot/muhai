"""/api/bank end to end, with a scripted bank behind it.

The router is stateless like /api/compute, so these need no database — only a
signed-in caller, which is overridden, and a bank, which is faked. What they
prove is the contract the Bank screen depends on: the shape of a statement,
the shape of a match, and which HTTP status each kind of failure produces.
"""
import json

import pytest

from app.services.bank_client import BankApiError, BankClient, BankCredentials, HttpResponse
from app.services.bank_providers import get_preset, resolve_provider
from tests.test_bank_client import FakeBank, _env, _json


@pytest.fixture
def signed_in(client):
    """A caller the API accepts, without a user table to read them from."""
    from app.api.deps import get_current_user
    from app.db.models.user import User
    from app.main import app

    app.dependency_overrides[get_current_user] = lambda: User(
        id="u1", email="owner@example.com", hashed_password="x", company_id="c1"
    )
    yield client
    app.dependency_overrides.clear()


@pytest.fixture
def with_bank(monkeypatch):
    """Point the router at a scripted bank instead of the live settings."""

    def _install(bank, **overrides):
        cfg = _env(**overrides)
        configured = BankClient(
            resolve_provider(cfg), BankCredentials.from_settings(cfg), bank
        )
        monkeypatch.setattr(
            "app.api.routes.bank.build_client", lambda *a, **k: configured
        )
        return configured

    return _install


def _statement(rows):
    return _json({"data": rows})


ROWS = [
    {
        "islemTarihi": "05.09.2026",
        "aciklama": "KIRA ODEMESI - TEKNOPARK GAYRIMENKUL AS",
        "tutar": "24.500,00",
        "borcAlacakKodu": "B",
    },
    {
        "islemTarihi": "06.09.2026",
        "aciklama": "FAST GELEN - ACME TEKNOLOJI AS",
        "tutar": "18.880,00",
        "borcAlacakKodu": "A",
    },
]

CSV = (
    "Tarih;Açıklama;Tutar\n"
    "05.09.2026;KIRA ÖDEMESİ - TEKNOPARK;-24.500,00\n"
    "06.09.2026;ELEKTRİK FATURASI - ENERJİSA;-3.417,50\n"
)


# ── Status ────────────────────────────────────────────────────────────


def test_status_explains_an_unconfigured_deployment(signed_in, monkeypatch):
    unconfigured = BankClient(get_preset("custom"), BankCredentials(), FakeBank())
    monkeypatch.setattr("app.api.routes.bank.build_client", lambda *a, **k: unconfigured)

    body = signed_in.get("/api/bank/status").json()
    assert body["configured"] is False
    assert "BANK_API_BASE_URL" in body["reason"]
    # CSV import never depended on the bank, so the screen keeps working.
    assert body["csv_import"] is True


def test_status_reports_a_connected_bank(signed_in, with_bank):
    with_bank(FakeBank())
    body = signed_in.get("/api/bank/status").json()
    assert body["configured"] is True
    assert body["live"] is True


def test_accounts_are_listed(signed_in, with_bank):
    with_bank(
        FakeBank(
            {
                "/oauth/token": [_json({"access_token": "t"})],
                "/accounts": [_json({"data": [{"accountId": "TR99", "hesapAdi": "Vadesiz"}]})],
            }
        )
    )
    accounts = signed_in.get("/api/bank/accounts").json()
    assert accounts[0]["id"] == "TR99"


# ── Fetch ─────────────────────────────────────────────────────────────


def test_transactions_are_fetched_categorised_and_summed(signed_in, with_bank):
    with_bank(
        FakeBank(
            {"/oauth/token": [_json({"access_token": "t"})], "/transactions": [_statement(ROWS)]}
        )
    )
    body = signed_in.post(
        "/api/bank/transactions",
        json={"account_id": "TR99", "since": "2026-09-01", "until": "2026-09-20"},
    ).json()

    assert body["summary"] == {
        "total": 2, "matched": 0, "unmatched": 2, "match_rate": 0.0,
        "money_in": 18880.0, "money_out": 24500.0, "net": -5620.0,
    }
    rent = [r for r in body["rows"] if r["direction"] == "out"][0]
    assert rent["category"] == "rent"
    # Every row carries the ledger document it would become, so the browser
    # never has to rebuild it.
    assert rent["ledger"]["type"] == "expense"
    assert rent["ledger"]["amount"] == 24500.0


def test_the_date_range_defaults_to_the_last_thirty_days(signed_in, with_bank):
    bank = FakeBank(
        {"/oauth/token": [_json({"access_token": "t"})], "/transactions": [_statement([])]}
    )
    with_bank(bank)
    body = signed_in.post("/api/bank/transactions", json={"account_id": "TR99"}).json()

    import datetime as dt

    assert body["until"] == dt.date.today().isoformat()
    assert body["since"] == (dt.date.today() - dt.timedelta(days=30)).isoformat()


# ── CSV ───────────────────────────────────────────────────────────────


def test_a_csv_statement_imports_without_any_bank_connection(signed_in, monkeypatch):
    unconfigured = BankClient(get_preset("custom"), BankCredentials(), FakeBank())
    monkeypatch.setattr("app.api.routes.bank.build_client", lambda *a, **k: unconfigured)

    response = signed_in.post(
        "/api/bank/import",
        files={"file": ("ekstre.csv", CSV.encode("utf-8"), "text/csv")},
    )
    body = response.json()

    assert response.status_code == 200
    assert body["source"] == "csv"
    assert body["summary"]["money_out"] == 27917.5
    assert [r["category"] for r in body["rows"]] == ["rent", "utilities"]


def test_a_windows_encoded_csv_keeps_its_turkish_characters(signed_in):
    response = signed_in.post(
        "/api/bank/import",
        files={"file": ("ekstre.csv", CSV.encode("cp1254"), "text/csv")},
    )
    assert "ÖDEMESİ" in response.json()["rows"][0]["description"]


def test_a_file_with_no_movements_is_rejected_with_a_readable_reason(signed_in):
    response = signed_in.post(
        "/api/bank/import", files={"file": ("x.csv", b"hello;world\n1;2\n", "text/csv")}
    )
    assert response.status_code == 422
    assert "işlem satırı" in response.json()["detail"]


def test_an_empty_file_is_rejected(signed_in):
    response = signed_in.post("/api/bank/import", files={"file": ("x.csv", b"", "text/csv")})
    assert response.status_code == 400


# ── Reconcile ─────────────────────────────────────────────────────────


def test_reconcile_matches_posted_rows_against_posted_invoices(signed_in):
    payload = {
        "rows": [
            {"date": "2026-09-07", "description": "KIRA ODEMESI - TEKNOPARK", "amount": -24500.0},
            {"date": "2026-09-08", "description": "BILINMEYEN ODEME", "amount": -1234.0},
        ],
        "invoices": [
            {
                "id": "inv1", "amount": 24500.0, "date": "2026-09-05",
                "vendor": "Teknopark Gayrimenkul A.Ş.", "direction": "purchase",
            }
        ],
    }
    body = signed_in.post("/api/bank/reconcile", json=payload).json()

    assert [m["status"] for m in body["matches"]] == ["matched", "unmatched"]
    assert body["matches"][0]["invoice_id"] == "inv1"
    assert body["matches"][0]["confidence"] >= 0.6
    assert body["summary"]["match_rate"] == 0.5


def test_reconcile_applies_the_learned_vendor_map(signed_in):
    payload = {
        "rows": [{"date": "2026-09-07", "description": "AYLIK ODEME", "amount": -900.0,
                  "counterparty": "Acme Teknoloji A.Ş."}],
        "invoices": [],
        "learned": {"Acme Teknoloji A.Ş.": "software"},
    }
    body = signed_in.post("/api/bank/reconcile", json=payload).json()
    assert body["rows"][0]["category"] == "software"


def test_reconcile_of_nothing_is_an_empty_statement(signed_in):
    body = signed_in.post("/api/bank/reconcile", json={}).json()
    assert body["rows"] == [] and body["matches"] == []
    assert body["summary"]["total"] == 0


# ── Sync ──────────────────────────────────────────────────────────────


def test_sync_fetches_and_matches_in_one_call(signed_in, with_bank):
    with_bank(
        FakeBank(
            {"/oauth/token": [_json({"access_token": "t"})], "/transactions": [_statement(ROWS)]}
        )
    )
    body = signed_in.post(
        "/api/bank/sync",
        json={
            "account_id": "TR99",
            "since": "2026-09-01",
            "until": "2026-09-20",
            "invoices": [
                {
                    "id": "inv1", "amount": 24500.0, "date": "2026-09-05",
                    "vendor": "Teknopark Gayrimenkul AS", "direction": "purchase",
                }
            ],
        },
    ).json()

    assert body["summary"]["matched"] == 1
    assert body["summary"]["unmatched"] == 1
    matched = [m for m in body["matches"] if m["status"] == "matched"][0]
    assert matched["invoice_id"] == "inv1"


# ── Failures ──────────────────────────────────────────────────────────


def test_an_unconfigured_bank_answers_503_so_the_ui_can_offer_csv(signed_in, monkeypatch):
    unconfigured = BankClient(get_preset("custom"), BankCredentials(), FakeBank())
    monkeypatch.setattr("app.api.routes.bank.build_client", lambda *a, **k: unconfigured)

    response = signed_in.post("/api/bank/sync", json={"account_id": "x"})
    assert response.status_code == 503
    assert "BANK_API_BASE_URL" in response.json()["detail"]


def test_a_rejected_consent_answers_502_with_the_bank_s_reason(signed_in, with_bank):
    with_bank(
        FakeBank(
            {
                "/oauth/token": [_json({"access_token": "t"})],
                "/transactions": [_json({"message": "consent expired"}, 403)],
            }
        )
    )
    response = signed_in.post("/api/bank/transactions", json={"account_id": "x"})
    assert response.status_code == 502
    assert "reddedildi" in response.json()["detail"]


def test_an_unreachable_bank_answers_504(signed_in, with_bank):
    with_bank(FakeBank({"": [BankApiError("Banka servisine ulaşılamadı.", status=0)]}))
    response = signed_in.post("/api/bank/transactions", json={"account_id": "x"})
    assert response.status_code == 504


def test_the_sample_provider_serves_a_statement_with_no_credentials(signed_in, monkeypatch):
    sample = BankClient(get_preset("mock"), BankCredentials(), FakeBank())
    monkeypatch.setattr("app.api.routes.bank.build_client", lambda *a, **k: sample)

    body = signed_in.post("/api/bank/sync", json={"account_id": "demo"}).json()
    assert body["source"] == "mock"
    assert body["summary"]["total"] == 8
    assert json.dumps(body)  # serialisable end to end
