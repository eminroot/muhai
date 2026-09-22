"""The bank transport: configuration, auth, retries, error mapping.

Every test drives the real ``BankClient`` against a scripted bank, so the
suite exercises the code that will run against a live gateway — the URL it
builds, the headers it sends, the token it caches — without a network.
"""
import datetime as dt
from types import SimpleNamespace

import pytest

from app.services.bank_client import (
    BankApiError,
    BankClient,
    BankCredentials,
    BankNotConfigured,
    HttpResponse,
    build_client,
)
from app.services.bank_providers import get_preset, resolve_provider

SINCE = dt.date(2026, 9, 1)
UNTIL = dt.date(2026, 9, 20)


class FakeBank:
    """A scripted bank. Records every request; replies from a queue per path."""

    def __init__(self, responses=None):
        self.responses = responses or {}
        self.requests = []

    def send(self, method, url, *, headers, body=None, timeout=20.0):
        self.requests.append(
            SimpleNamespace(method=method, url=url, headers=headers, body=body, timeout=timeout)
        )
        path = url.split("?")[0]
        for key, queue in self.responses.items():
            if key in path:
                reply = queue.pop(0) if len(queue) > 1 else queue[0]
                if isinstance(reply, Exception):
                    raise reply
                return reply
        return HttpResponse(200, b"[]")


def _json(payload, status=200):
    import json

    return HttpResponse(status, json.dumps(payload).encode("utf-8"))


def _env(**overrides):
    base = {
        "BANK_PROVIDER": "custom",
        "BANK_API_BASE_URL": "https://sandbox.example-bank.com.tr/v1",
        "BANK_TOKEN_URL": "https://sandbox.example-bank.com.tr/oauth/token",
        "BANK_CLIENT_ID": "id-123",
        "BANK_CLIENT_SECRET": "secret-456",
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def _client(bank, **overrides):
    cfg = _env(**overrides)
    return BankClient(resolve_provider(cfg), BankCredentials.from_settings(cfg), bank)


# ── Configuration ─────────────────────────────────────────────────────


def test_an_unconfigured_deployment_says_exactly_what_is_missing():
    client = BankClient(get_preset("custom"), BankCredentials(), FakeBank())
    assert not client.is_configured
    assert "BANK_API_BASE_URL" in client.configuration_error()

    cfg = _env(BANK_CLIENT_ID="", BANK_CLIENT_SECRET="")
    client = BankClient(resolve_provider(cfg), BankCredentials.from_settings(cfg), FakeBank())
    assert "BANK_CLIENT_ID" in client.configuration_error()


def test_status_reports_a_usable_connection():
    status = _client(FakeBank()).status()
    assert status["configured"] is True
    assert status["live"] is True
    assert status["auth"] == "oauth2_client_credentials"
    assert status["reason"] is None


def test_an_unconfigured_call_raises_before_touching_the_network():
    bank = FakeBank()
    client = BankClient(get_preset("custom"), BankCredentials(), bank)
    with pytest.raises(BankNotConfigured):
        client.list_transactions("acc", SINCE, UNTIL)
    assert bank.requests == []


def test_environment_overrides_beat_the_preset():
    provider = resolve_provider(
        _env(
            BANK_PROVIDER="garanti",
            BANK_TRANSACTIONS_PATH="/hesap/hareketler",
            BANK_SINCE_PARAM="baslangicTarihi",
            BANK_DATE_FORMAT="%d.%m.%Y",
            BANK_FIELD_MAP='{"amount": ["islemTutariTL"]}',
        )
    )
    assert provider.key == "garanti"
    assert provider.transactions_path == "/hesap/hareketler"
    assert provider.since_param == "baslangicTarihi"
    assert provider.fields.amount[0] == "islemTutariTL"


def test_a_malformed_field_map_is_ignored_rather_than_fatal():
    provider = resolve_provider(_env(BANK_FIELD_MAP="{not json"))
    assert provider.fields.amount[0] == "amount"


def test_an_unknown_provider_name_falls_back_to_custom():
    assert resolve_provider(_env(BANK_PROVIDER="not-a-bank")).key == "custom"


# ── The sample provider ───────────────────────────────────────────────


def test_the_sample_provider_needs_no_credentials_and_no_network():
    bank = FakeBank({"": [RuntimeError("the sample provider must not call out")]})
    client = BankClient(get_preset("mock"), BankCredentials(), bank)

    assert client.is_configured
    assert client.status()["live"] is False

    rows = client.list_transactions("any", SINCE, UNTIL)
    assert bank.requests == []
    assert len(rows) == 8
    assert any(r.amount > 0 for r in rows) and any(r.amount < 0 for r in rows)
    assert client.list_accounts()[0]["currency"] == "TRY"


# ── OAuth ─────────────────────────────────────────────────────────────


def test_the_token_is_requested_once_and_reused():
    bank = FakeBank(
        {
            "/oauth/token": [_json({"access_token": "tok-1", "expires_in": 3600})],
            "/transactions": [_json({"data": []})],
        }
    )
    client = _client(bank)

    client.list_transactions("acc-1", SINCE, UNTIL)
    client.list_transactions("acc-1", SINCE, UNTIL)

    token_calls = [r for r in bank.requests if "token" in r.url]
    assert len(token_calls) == 1
    assert token_calls[0].method == "POST"
    assert b"grant_type=client_credentials" in token_calls[0].body
    assert all(
        r.headers["Authorization"] == "Bearer tok-1"
        for r in bank.requests
        if "transactions" in r.url
    )


def test_an_expired_token_is_refreshed():
    """The clock is injected so this does not depend on real time passing."""
    bank = FakeBank(
        {
            "/oauth/token": [
                _json({"access_token": "tok-1", "expires_in": 120}),
                _json({"access_token": "tok-2", "expires_in": 120}),
            ],
            "/transactions": [_json({"data": []})],
        }
    )
    now = [0.0]
    cfg = _env()
    client = BankClient(
        resolve_provider(cfg), BankCredentials.from_settings(cfg), bank, clock=lambda: now[0]
    )

    client.list_transactions("acc-1", SINCE, UNTIL)
    now[0] = 200.0  # past the 120s lifetime
    client.list_transactions("acc-1", SINCE, UNTIL)

    assert len([r for r in bank.requests if "token" in r.url]) == 2
    assert bank.requests[-1].headers["Authorization"] == "Bearer tok-2"


def test_a_token_response_without_a_token_is_an_error():
    bank = FakeBank({"/oauth/token": [_json({"error": "invalid_client"})]})
    with pytest.raises(BankApiError):
        _client(bank).list_transactions("acc-1", SINCE, UNTIL)


def test_a_static_bearer_skips_the_token_endpoint():
    bank = FakeBank({"/transactions": [_json({"data": []})]})
    client = _client(bank, BANK_AUTH_STYLE="static_bearer", BANK_ACCESS_TOKEN="static-tok")

    client.list_transactions("acc-1", SINCE, UNTIL)
    assert not [r for r in bank.requests if "token" in r.url]
    assert bank.requests[0].headers["Authorization"] == "Bearer static-tok"


def test_an_api_key_goes_in_the_header_the_bank_names():
    bank = FakeBank({"/transactions": [_json({"data": []})]})
    client = _client(
        bank,
        BANK_AUTH_STYLE="api_key_header",
        BANK_API_KEY="key-789",
        BANK_API_KEY_HEADER="X-IBM-Client-Id",
    )

    client.list_transactions("acc-1", SINCE, UNTIL)
    assert bank.requests[0].headers["X-IBM-Client-Id"] == "key-789"


def test_consent_and_extra_headers_travel_on_every_call():
    bank = FakeBank(
        {"/oauth/token": [_json({"access_token": "t"})], "/transactions": [_json({"data": []})]}
    )
    client = _client(
        bank,
        BANK_CONSENT_ID="consent-1",
        BANK_EXTRA_HEADERS='{"X-Channel": "MUHAI"}',
    )

    client.list_transactions("acc-1", SINCE, UNTIL)
    call = [r for r in bank.requests if "transactions" in r.url][0]
    assert call.headers["Consent-ID"] == "consent-1"
    assert call.headers["X-Channel"] == "MUHAI"


# ── Request building ──────────────────────────────────────────────────


def test_the_account_and_date_range_land_in_the_url():
    bank = FakeBank(
        {"/oauth/token": [_json({"access_token": "t"})], "/transactions": [_json({"data": []})]}
    )
    client = _client(bank, BANK_DATE_FORMAT="%d.%m.%Y")
    client.list_transactions("TR99 0001", SINCE, UNTIL)

    url = [r for r in bank.requests if "transactions" in r.url][0].url
    assert "/accounts/TR99%200001/transactions" in url
    assert "startDate=01.09.2026" in url
    assert "endDate=20.09.2026" in url


def test_a_bank_that_wants_the_account_as_a_query_parameter():
    bank = FakeBank(
        {"/oauth/token": [_json({"access_token": "t"})], "/hareketler": [_json({"data": []})]}
    )
    client = _client(bank, BANK_TRANSACTIONS_PATH="/hareketler")
    client.list_transactions("acc-7", SINCE, UNTIL)

    url = [r for r in bank.requests if "hareketler" in r.url][0].url
    assert "accountId=acc-7" in url


def test_transactions_come_back_newest_first_and_capped():
    payload = {
        "data": [
            {"tarih": f"2026-09-{day:02d}", "tutar": "-100,00", "aciklama": "X"}
            for day in range(1, 11)
        ]
    }
    bank = FakeBank(
        {"/oauth/token": [_json({"access_token": "t"})], "/transactions": [_json(payload)]}
    )
    rows = _client(bank).list_transactions("acc", SINCE, UNTIL, limit=3)

    assert len(rows) == 3
    assert rows[0].date == dt.date(2026, 9, 10)


# ── Failures ──────────────────────────────────────────────────────────


def test_a_server_error_is_retried_and_then_succeeds():
    bank = FakeBank(
        {
            "/oauth/token": [_json({"access_token": "t"})],
            "/transactions": [_json({"message": "busy"}, 503), _json({"data": []})],
        }
    )
    assert _client(bank).list_transactions("acc", SINCE, UNTIL) == []
    assert len([r for r in bank.requests if "transactions" in r.url]) == 2


def test_a_rejected_call_is_not_retried():
    """A 403 is a decision about consent or scope. Repeating it wastes the
    user's time and the bank's rate limit."""
    bank = FakeBank(
        {
            "/oauth/token": [_json({"access_token": "t"})],
            "/transactions": [_json({"message": "consent expired"}, 403)],
        }
    )
    with pytest.raises(BankApiError) as excinfo:
        _client(bank).list_transactions("acc", SINCE, UNTIL)

    assert excinfo.value.status == 403
    assert "reddedildi" in excinfo.value.message
    assert excinfo.value.detail == "consent expired"
    assert len([r for r in bank.requests if "transactions" in r.url]) == 1


def test_a_transport_failure_reports_status_zero():
    bank = FakeBank({"": [BankApiError("Banka servisine ulaşılamadı.", status=0)]})
    with pytest.raises(BankApiError) as excinfo:
        _client(bank).list_transactions("acc", SINCE, UNTIL)
    assert excinfo.value.status == 0


def test_a_non_json_body_is_reported_as_such():
    bank = FakeBank(
        {"/oauth/token": [_json({"access_token": "t"})], "/transactions": [HttpResponse(200, b"<html>")]}
    )
    with pytest.raises(BankApiError) as excinfo:
        _client(bank).list_transactions("acc", SINCE, UNTIL)
    assert "JSON" in excinfo.value.message


# ── Factory ───────────────────────────────────────────────────────────


def test_build_client_reads_the_live_settings_and_defaults_to_unconfigured():
    """Shipped defaults connect to nothing, which is the intended state until
    an operator pastes real credentials into .env."""
    client = build_client()
    assert client.provider.key in ("custom", "mock")
    if client.provider.auth != "none":
        assert not client.is_configured
