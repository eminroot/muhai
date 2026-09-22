"""The bank API transport: authenticate, call, retry, normalise.

Standard library only — ``urllib`` plus ``ssl`` — for the same reason the
Gemini backend is: no new dependency, no image rebuild, and nothing fetched at
runtime. The whole point of Muhai is that it runs on a VPS with Docker and
nothing else.

Three things here are not optional for a Turkish bank gateway and are easy to
discover the hard way:

* **OAuth2 client credentials with a cached token.** Requesting a token per
  call is how a client gets rate-limited off a production gateway. The token is
  reused until a minute before it expires.
* **Mutual TLS.** Most regulated open-banking endpoints want a client
  certificate, so ``BANK_CLIENT_CERT``/``BANK_CLIENT_KEY`` build an SSL context
  rather than being left for someone to bolt on later.
* **Retry on 429 and 5xx, never on 4xx.** Retrying a rejected consent just
  turns one clear error into four slow ones.

The network sits behind a ``Transport`` seam, so every test in the suite runs
the real client against a scripted bank and no test needs an internet
connection.
"""
from __future__ import annotations

import datetime as dt
import json
import logging
import ssl
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Protocol

from app.services import bank_service as bs
from app.services.bank_providers import BankProvider, resolve_provider

logger = logging.getLogger(__name__)

# Tokens are re-requested this many seconds before the bank says they expire,
# so a call in flight cannot land on the far side of the expiry.
TOKEN_REFRESH_MARGIN_SECONDS = 60
DEFAULT_TIMEOUT_SECONDS = 20.0
MAX_ATTEMPTS = 3


class BankApiError(Exception):
    """A bank call that failed, with a message a user can be shown.

    ``status`` is the HTTP status where there was one, 0 for a transport
    failure — the same convention the web client uses, so "the bank is
    unreachable" and "the bank said no" stay distinguishable all the way to
    the screen.
    """

    def __init__(self, message: str, *, status: int = 0, detail: str | None = None):
        super().__init__(message)
        self.message = message
        self.status = status
        self.detail = detail


class BankNotConfigured(BankApiError):
    """No usable connection — missing base URL or credentials."""

    def __init__(self, message: str):
        super().__init__(message, status=0)


# ── Transport ─────────────────────────────────────────────────────────


@dataclass
class HttpResponse:
    status: int
    body: bytes
    headers: dict[str, str] = field(default_factory=dict)

    def json(self) -> Any:
        if not self.body:
            return {}
        try:
            return json.loads(self.body.decode("utf-8"))
        except (ValueError, UnicodeDecodeError) as exc:
            raise BankApiError(
                "Banka beklenmeyen bir yanıt döndürdü (JSON değil).",
                status=self.status,
                detail=str(exc),
            ) from exc


class Transport(Protocol):
    def send(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str],
        body: bytes | None = None,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> HttpResponse:
        ...


class UrllibTransport:
    """The real one. Builds an SSL context once, then just makes requests."""

    def __init__(self, ssl_context: ssl.SSLContext | None = None):
        self._ssl_context = ssl_context

    def send(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str],
        body: bytes | None = None,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> HttpResponse:
        request = urllib.request.Request(url, data=body, headers=headers, method=method)
        try:
            with urllib.request.urlopen(
                request, timeout=timeout, context=self._ssl_context
            ) as response:
                return HttpResponse(
                    status=response.status,
                    body=response.read(),
                    headers={k.lower(): v for k, v in response.headers.items()},
                )
        except urllib.error.HTTPError as exc:
            # An error body is still a body — banks put the useful part there.
            return HttpResponse(
                status=exc.code,
                body=exc.read() or b"",
                headers={k.lower(): v for k, v in (exc.headers or {}).items()},
            )
        except urllib.error.URLError as exc:
            raise BankApiError(
                "Banka servisine ulaşılamadı.", status=0, detail=str(exc.reason)
            ) from exc
        except TimeoutError as exc:
            raise BankApiError(
                "Banka servisi zaman aşımına uğradı.", status=0, detail=str(exc)
            ) from exc


# ── Credentials ───────────────────────────────────────────────────────


@dataclass(frozen=True)
class BankCredentials:
    client_id: str = ""
    client_secret: str = ""
    api_key: str = ""
    access_token: str = ""
    consent_id: str = ""
    extra_headers: dict[str, str] = field(default_factory=dict)
    client_cert: str = ""
    client_key: str = ""
    ca_bundle: str = ""
    verify_tls: bool = True
    timeout: float = DEFAULT_TIMEOUT_SECONDS

    @classmethod
    def from_settings(cls, cfg: Any) -> "BankCredentials":
        raw_headers = (getattr(cfg, "BANK_EXTRA_HEADERS", "") or "").strip()
        headers: dict[str, str] = {}
        if raw_headers:
            try:
                parsed = json.loads(raw_headers)
                if isinstance(parsed, dict):
                    headers = {str(k): str(v) for k, v in parsed.items()}
            except ValueError:
                logger.warning("BANK_EXTRA_HEADERS is not valid JSON; ignoring it.")

        return cls(
            client_id=(getattr(cfg, "BANK_CLIENT_ID", "") or "").strip(),
            client_secret=(getattr(cfg, "BANK_CLIENT_SECRET", "") or "").strip(),
            api_key=(getattr(cfg, "BANK_API_KEY", "") or "").strip(),
            access_token=(getattr(cfg, "BANK_ACCESS_TOKEN", "") or "").strip(),
            consent_id=(getattr(cfg, "BANK_CONSENT_ID", "") or "").strip(),
            extra_headers=headers,
            client_cert=(getattr(cfg, "BANK_CLIENT_CERT", "") or "").strip(),
            client_key=(getattr(cfg, "BANK_CLIENT_KEY", "") or "").strip(),
            ca_bundle=(getattr(cfg, "BANK_CA_BUNDLE", "") or "").strip(),
            verify_tls=bool(getattr(cfg, "BANK_VERIFY_TLS", True)),
            timeout=float(getattr(cfg, "BANK_TIMEOUT_SECONDS", DEFAULT_TIMEOUT_SECONDS)),
        )


def build_ssl_context(credentials: BankCredentials) -> ssl.SSLContext | None:
    """Client certificate + CA bundle, when the gateway asks for them."""
    if not (credentials.client_cert or credentials.ca_bundle or not credentials.verify_tls):
        return None

    context = ssl.create_default_context(
        cafile=credentials.ca_bundle or None
    )
    if not credentials.verify_tls:
        # Only ever for a bank's own sandbox with a self-signed chain. Loud on
        # purpose: this must never be how a production deployment is left.
        logger.warning("BANK_VERIFY_TLS=false — bank TLS certificate is NOT verified.")
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
    if credentials.client_cert:
        context.load_cert_chain(
            certfile=credentials.client_cert,
            keyfile=credentials.client_key or None,
        )
    return context


# ── The sample bank ───────────────────────────────────────────────────


def _mock_payload(since: dt.date, until: dt.date) -> list[dict]:
    """A deterministic statement, in a deliberately awkward shape.

    Turkish dates, comma decimals, a borç/alacak flag and a nested amount —
    the same shapes the normaliser has to survive against a real bank. So this
    demonstrates the pipeline rather than a tidy path built for itself.
    """
    day = since
    rows = [
        ("FAST GELEN - ACME TEKNOLOJI A.S. - FATURA 2026-0041", "18.880,00", "A"),
        ("KIRA ODEMESI - TEKNOPARK GAYRIMENKUL AS", "24.500,00", "B"),
        ("ELEKTRIK FATURASI - ENERJISA", "3.417,50", "B"),
        ("MAAS ODEMESI - PERSONEL", "112.000,00", "B"),
        ("HAVALE GELEN - BETA LOJISTIK LTD STI", "7.080,00", "A"),
        ("KDV ODEMESI - GIB", "9.240,00", "B"),
        ("HESAP ISLETIM UCRETI", "185,00", "B"),
        ("POS TAHSILATI", "4.250,75", "A"),
    ]
    payload = []
    step = max((until - since).days // max(len(rows), 1), 1)
    for index, (description, amount, flag) in enumerate(rows):
        when = min(day + dt.timedelta(days=step * index), until)
        payload.append(
            {
                "islemTarihi": when.strftime("%d.%m.%Y"),
                "aciklama": description,
                "tutar": {"value": amount, "currency": "TRY"},
                "borcAlacakKodu": flag,
                "referansNo": f"MOCK{index:04d}",
            }
        )
    return payload


_MOCK_ACCOUNTS = [
    {
        "accountId": "TR000000000000000000000001",
        "hesapAdi": "Vadesiz TL Hesabı",
        "iban": "TR00 0000 0000 0000 0000 0000 01",
        "paraBirimi": "TRY",
        "kullanilabilirBakiye": "284.920,45",
    }
]


# ── Client ────────────────────────────────────────────────────────────


class BankClient:
    """One configured bank connection."""

    def __init__(
        self,
        provider: BankProvider,
        credentials: BankCredentials,
        transport: Transport | None = None,
        *,
        clock: Any = time.monotonic,
    ):
        self.provider = provider
        self.credentials = credentials
        self._transport = transport or UrllibTransport(build_ssl_context(credentials))
        self._clock = clock
        self._token: str = ""
        self._token_expires_at: float = 0.0
        self._lock = threading.Lock()

    # ── Configuration ────────────────────────────────────────────────
    def configuration_error(self) -> str | None:
        """Why this connection cannot be used, in one Turkish sentence.

        Checked before every call and surfaced by ``/api/bank/status``, so the
        UI can say "set BANK_CLIENT_ID" instead of showing a failed request.
        """
        provider = self.provider
        if provider.auth == "none":
            return None
        if not provider.base_url:
            return "BANK_API_BASE_URL tanımlı değil — bankanın API adresi gerekli."
        if provider.auth == "oauth2_client_credentials":
            if not (self.credentials.client_id and self.credentials.client_secret):
                return "BANK_CLIENT_ID ve BANK_CLIENT_SECRET tanımlı değil."
            if not (provider.token_url or self.credentials.access_token):
                return "BANK_TOKEN_URL tanımlı değil — token adresi gerekli."
        elif provider.auth == "static_bearer" and not self.credentials.access_token:
            return "BANK_ACCESS_TOKEN tanımlı değil."
        elif provider.auth == "api_key_header" and not self.credentials.api_key:
            return "BANK_API_KEY tanımlı değil."
        return None

    @property
    def is_configured(self) -> bool:
        return self.configuration_error() is None

    def status(self) -> dict[str, Any]:
        error = self.configuration_error()
        return {
            "provider": self.provider.key,
            "display_name": self.provider.display_name,
            "auth": self.provider.auth,
            "configured": error is None,
            "live": error is None and self.provider.auth != "none",
            "reason": error,
            "portal": self.provider.portal or None,
            "base_url": self.provider.base_url or None,
            "notes": self.provider.notes or None,
        }

    # ── Auth ─────────────────────────────────────────────────────────
    def _absolute(self, path: str) -> str:
        if path.startswith(("http://", "https://")):
            return path
        return f"{self.provider.base_url.rstrip('/')}/{path.lstrip('/')}"

    def _fetch_token(self) -> str:
        """OAuth2 client-credentials grant, cached until just before expiry."""
        now = self._clock()
        with self._lock:
            if self._token and now < self._token_expires_at:
                return self._token

            body = {"grant_type": "client_credentials"}
            if self.provider.scope:
                body["scope"] = self.provider.scope
            # Credentials in the form body rather than Basic auth: it is what
            # every Turkish portal sample uses, and both are allowed by RFC 6749.
            body["client_id"] = self.credentials.client_id
            body["client_secret"] = self.credentials.client_secret

            response = self._send(
                "POST",
                self._absolute(self.provider.token_url),
                headers={
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Accept": "application/json",
                },
                body=urllib.parse.urlencode(body).encode("utf-8"),
                authenticated=False,
            )
            payload = response.json()
            token = str(
                payload.get("access_token") or payload.get("accessToken") or ""
            ).strip()
            if not token:
                raise BankApiError(
                    "Banka bir erişim tokenı döndürmedi.",
                    status=response.status,
                    detail=json.dumps(payload)[:400],
                )

            try:
                lifetime = float(payload.get("expires_in") or payload.get("expiresIn") or 300)
            except (TypeError, ValueError):
                lifetime = 300.0

            self._token = token
            self._token_expires_at = now + max(lifetime - TOKEN_REFRESH_MARGIN_SECONDS, 30)
            return token

    def _auth_headers(self) -> dict[str, str]:
        headers: dict[str, str] = {}
        auth = self.provider.auth

        if auth == "oauth2_client_credentials":
            token = self.credentials.access_token or self._fetch_token()
            headers["Authorization"] = f"Bearer {token}"
        elif auth == "static_bearer":
            headers["Authorization"] = f"Bearer {self.credentials.access_token}"
        elif auth == "api_key_header":
            headers[self.provider.api_key_header] = self.credentials.api_key

        # Many gateways want the key *as well as* the bearer.
        if self.credentials.api_key and auth != "api_key_header":
            headers.setdefault(self.provider.api_key_header, self.credentials.api_key)
        if self.credentials.consent_id:
            headers.setdefault("Consent-ID", self.credentials.consent_id)
        headers.update(self.credentials.extra_headers)
        return headers

    # ── Requests ─────────────────────────────────────────────────────
    def _send(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        body: bytes | None = None,
        authenticated: bool = True,
    ) -> HttpResponse:
        request_headers: dict[str, str] = {"Accept": "application/json"}
        if authenticated:
            request_headers.update(self._auth_headers())
        request_headers.update(headers or {})

        last_error: BankApiError | None = None
        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                response = self._transport.send(
                    method,
                    url,
                    headers=request_headers,
                    body=body,
                    timeout=self.credentials.timeout,
                )
            except BankApiError as exc:
                last_error = exc
                if attempt == MAX_ATTEMPTS:
                    raise
                time.sleep(0.2 * attempt)
                continue

            if response.status < 400:
                return response

            # 429 and 5xx are worth another attempt; a 4xx is a decision.
            if response.status in (429,) or response.status >= 500:
                last_error = _http_error(response)
                if attempt == MAX_ATTEMPTS:
                    raise last_error
                time.sleep(0.4 * attempt)
                continue

            raise _http_error(response)

        raise last_error or BankApiError("Banka çağrısı başarısız oldu.")

    def _get_json(self, path: str, params: dict[str, Any] | None = None) -> Any:
        query = urllib.parse.urlencode(
            {k: v for k, v in (params or {}).items() if v not in (None, "")}
        )
        url = self._absolute(path) + (f"?{query}" if query else "")
        return self._send("GET", url).json()

    # ── Operations ───────────────────────────────────────────────────
    def list_accounts(self) -> list[dict]:
        if self.provider.auth == "none":
            return bs.normalize_accounts(_MOCK_ACCOUNTS, self.provider.fields)

        error = self.configuration_error()
        if error:
            raise BankNotConfigured(error)

        body = self._get_json(self.provider.accounts_path)
        return bs.normalize_accounts(
            bs.extract_list(body, self.provider.list_keys), self.provider.fields
        )

    def list_transactions(
        self,
        account_id: str,
        since: dt.date,
        until: dt.date,
        *,
        limit: int = 500,
    ) -> list[bs.BankTxn]:
        if self.provider.auth == "none":
            records = _mock_payload(since, until)
            return bs.normalize_records(records, self.provider.fields, source="api")

        error = self.configuration_error()
        if error:
            raise BankNotConfigured(error)

        path = self.provider.transactions_path.replace(
            "{account_id}", urllib.parse.quote(str(account_id), safe="")
        )
        params = {
            self.provider.since_param: since.strftime(self.provider.date_format),
            self.provider.until_param: until.strftime(self.provider.date_format),
        }
        # A bank that wants the account as a query parameter says so by leaving
        # {account_id} out of the path.
        if "{account_id}" not in self.provider.transactions_path and account_id:
            params.setdefault("accountId", account_id)

        body = self._get_json(path, params)
        rows = bs.normalize_records(
            bs.extract_list(body, self.provider.list_keys),
            self.provider.fields,
            source="api",
        )
        rows.sort(key=lambda r: (r.date or dt.date.min), reverse=True)
        return rows[:limit]


def _http_error(response: HttpResponse) -> BankApiError:
    """Turn a bank's error body into one sentence, keeping the detail."""
    detail = ""
    try:
        payload = json.loads(response.body.decode("utf-8")) if response.body else {}
        if isinstance(payload, dict):
            for key in ("message", "error_description", "error", "detail", "hata", "mesaj"):
                value = payload.get(key)
                if isinstance(value, str) and value:
                    detail = value
                    break
    except (ValueError, UnicodeDecodeError):
        detail = response.body[:200].decode("utf-8", "replace") if response.body else ""

    if response.status in (401, 403):
        message = "Banka kimlik bilgileri reddedildi (yetki veya onay hatası)."
    elif response.status == 404:
        message = "Banka bu hesabı ya da uç noktayı bulamadı."
    elif response.status == 429:
        message = "Banka istek sınırına ulaşıldı; biraz sonra tekrar deneyin."
    elif response.status >= 500:
        message = "Banka servisi şu anda hata veriyor."
    else:
        message = f"Banka çağrısı reddedildi (HTTP {response.status})."

    return BankApiError(message, status=response.status, detail=detail or None)


# ── Factory ───────────────────────────────────────────────────────────


def build_client(cfg: Any = None, transport: Transport | None = None) -> BankClient:
    """The client this deployment is configured for.

    Built per request rather than cached: it is a few object allocations, and
    a cached client would hold a token that outlives a configuration change.
    """
    if cfg is None:
        from app.core.config import settings as cfg

    return BankClient(
        provider=resolve_provider(cfg),
        credentials=BankCredentials.from_settings(cfg),
        transport=transport,
    )
