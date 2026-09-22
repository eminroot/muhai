"""Verification of Firebase ID tokens, for "sign in with Google".

The browser talks to Firebase, gets an ID token back, and posts it here. This
module checks that token is genuine and then the auth route exchanges it for a
Muhai session. **Google never becomes the session.** The token Muhai issues is
still its own, still signed with SECRET_KEY, and still the thing that scopes
every `/api/workspace` query to a company — so the rule the rest of the API
depends on, that the bearer token *is* the company scope, is untouched.

There is no `firebase-admin` here and no service-account key. A Firebase ID
token is an ordinary RS256 JWT signed by Google, and verifying one needs only
Google's published certificates plus the project id — both public. That keeps
the runtime image as it is and means no private credential has to be stored on
the VPS to accept a sign-in.

What is checked, and why each one matters:

* **signature** against the certificate named by the token's `kid`
* **`aud`** equals the project id — a token minted for somebody else's
  Firebase project must not open an account here
* **`iss`** is `securetoken.google.com/<project>` — rejects tokens from
  Google's other issuers, which have different audiences and lifetimes
* **`exp` / `iat`**, with a small skew allowance
* **`sub`** is non-empty; it is the Firebase uid
* **`sign_in_provider`** is `google.com`

That last one is the important one. The Firebase project may have other
sign-in methods switched on — anonymous, email/password, another app sharing
the same project. Without this check, a token from *any* of them would be a
valid Muhai account. Accepting only Google keeps this endpoint doing exactly
what the button on the page says it does.
"""
from __future__ import annotations

import asyncio
import json
import time
import urllib.error
import urllib.request
from typing import Any

from cryptography.hazmat.primitives import serialization
from cryptography.x509 import load_pem_x509_certificate
from jose import JWTError, jwt

# Google publishes the public half of the keys it signs Firebase ID tokens
# with here, as x509 certificates keyed by `kid`. They rotate; the response
# carries a Cache-Control max-age saying for how long.
CERT_URL = (
    "https://www.googleapis.com/robot/v1/metadata/x509/"
    "securetoken@system.gserviceaccount.com"
)

ISSUER_PREFIX = "https://securetoken.google.com/"

# Clocks drift. A minute is the usual allowance and is small enough that an
# expired token stays expired in any sense that matters.
LEEWAY_SECONDS = 60

_FETCH_TIMEOUT = 8


class GoogleIdentityError(Exception):
    """The token is missing, malformed, expired or not ours to accept."""


class _CertCache:
    """Google's signing certificates, held until they expire.

    Fetching on every sign-in would put a network round trip inside the login
    path — and a Google outage would then take sign-in down with it. The
    cache also keeps the last good set past its expiry as a fallback, so a
    refresh that fails does not immediately break logins.
    """

    def __init__(self) -> None:
        self._certs: dict[str, str] = {}
        self._expires_at: float = 0.0

    def _fetch(self) -> tuple[dict[str, str], float]:
        request = urllib.request.Request(CERT_URL, headers={"Accept": "application/json"})
        with urllib.request.urlopen(request, timeout=_FETCH_TIMEOUT) as response:
            body = response.read().decode("utf-8")
            cache_control = response.headers.get("Cache-Control", "")

        max_age = 3600
        for part in cache_control.split(","):
            part = part.strip()
            if part.startswith("max-age="):
                try:
                    max_age = int(part.split("=", 1)[1])
                except ValueError:
                    pass
                break

        return json.loads(body), time.time() + max_age

    def get(self, *, force: bool = False) -> dict[str, str]:
        if not force and self._certs and time.time() < self._expires_at:
            return self._certs
        try:
            certs, expires_at = self._fetch()
        except (urllib.error.URLError, OSError, ValueError) as exc:
            if self._certs:
                # Stale but real. Better than refusing every sign-in because
                # one refresh timed out.
                return self._certs
            raise GoogleIdentityError(
                "Google'ın imza sertifikalarına ulaşılamadı."
            ) from exc
        self._certs = certs
        self._expires_at = expires_at
        return certs


_cache = _CertCache()


def _public_key_pem(certificate: str) -> str:
    cert = load_pem_x509_certificate(certificate.encode("utf-8"))
    return cert.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")


def verify_id_token(id_token: str, project_id: str) -> dict[str, Any]:
    """Return the claims of a valid Google-issued Firebase ID token.

    Raises GoogleIdentityError for anything that is not one.
    """
    if not project_id:
        raise GoogleIdentityError("Google ile giriş bu sunucuda yapılandırılmamış.")
    if not id_token or not isinstance(id_token, str):
        raise GoogleIdentityError("Kimlik doğrulama anahtarı eksik.")

    try:
        header = jwt.get_unverified_header(id_token)
    except JWTError as exc:
        raise GoogleIdentityError("Kimlik doğrulama anahtarı okunamadı.") from exc

    kid = header.get("kid")
    if not kid:
        raise GoogleIdentityError("Kimlik doğrulama anahtarı eksik alan içeriyor.")
    if header.get("alg") != "RS256":
        # Firebase signs with RS256. Anything else is a token we do not know
        # how to trust — including `alg: none`.
        raise GoogleIdentityError("Beklenmeyen imza algoritması.")

    certs = _cache.get()
    certificate = certs.get(kid)
    if certificate is None:
        # A rotation we have not picked up yet: refetch once before giving up.
        certs = _cache.get(force=True)
        certificate = certs.get(kid)
    if certificate is None:
        raise GoogleIdentityError("Kimlik doğrulama anahtarı tanınmadı.")

    try:
        claims = jwt.decode(
            id_token,
            _public_key_pem(certificate),
            algorithms=["RS256"],
            audience=project_id,
            issuer=f"{ISSUER_PREFIX}{project_id}",
            options={"leeway": LEEWAY_SECONDS, "verify_at_hash": False},
        )
    except JWTError as exc:
        raise GoogleIdentityError("Google oturumu doğrulanamadı.") from exc

    if not claims.get("sub"):
        raise GoogleIdentityError("Google oturumu bir kullanıcıya bağlı değil.")

    provider = (claims.get("firebase") or {}).get("sign_in_provider")
    if provider != "google.com":
        raise GoogleIdentityError("Bu uç nokta yalnızca Google ile girişi kabul eder.")

    email = (claims.get("email") or "").strip().lower()
    if not email:
        raise GoogleIdentityError("Google hesabında e-posta adresi bulunamadı.")
    if claims.get("email_verified") is False:
        raise GoogleIdentityError("Google hesabının e-posta adresi doğrulanmamış.")

    claims["email"] = email
    return claims


async def verify_id_token_async(id_token: str, project_id: str) -> dict[str, Any]:
    """`verify_id_token` off the event loop.

    The certificate fetch is a blocking socket read, and on a cache miss it
    would otherwise stall every other request in flight.
    """
    return await asyncio.to_thread(verify_id_token, id_token, project_id)
