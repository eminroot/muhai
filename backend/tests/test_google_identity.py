"""Firebase ID token verification.

Every test mints a real RS256 token with a throwaway key and feeds the
matching certificate to the module's cache, so the checks are exercised
against genuine signatures rather than stubs. Only the network fetch is
replaced.

The negative cases are the point: each one is a token that would open a Muhai
account if the corresponding check were dropped.
"""
import base64
import datetime
import json
import time

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from jose import jwt

from app.services import google_identity
from app.services.google_identity import GoogleIdentityError, verify_id_token

PROJECT = "cyberxbank-7dc0b"
KID = "test-key-1"


def _keypair():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name(
        [x509.NameAttribute(NameOID.COMMON_NAME, "securetoken.test")]
    )
    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(days=1))
        .not_valid_after(now + datetime.timedelta(days=1))
        .sign(key, hashes.SHA256())
    )
    pem_key = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()
    pem_cert = cert.public_bytes(serialization.Encoding.PEM).decode()
    return pem_key, pem_cert


PRIVATE_PEM, CERT_PEM = _keypair()


@pytest.fixture(autouse=True)
def _certs(monkeypatch):
    """Serve our certificate instead of reaching out to Google."""
    monkeypatch.setattr(
        google_identity._cache, "get", lambda force=False: {KID: CERT_PEM}
    )


def make_token(**overrides):
    now = int(time.time())
    claims = {
        "iss": f"https://securetoken.google.com/{PROJECT}",
        "aud": PROJECT,
        "sub": "firebase-uid-123",
        "iat": now - 30,
        "exp": now + 3600,
        "auth_time": now - 30,
        "email": "Emin@Example.com",
        "email_verified": True,
        "name": "Emin Baxishli",
        "firebase": {"sign_in_provider": "google.com"},
    }
    claims.update(overrides)
    return jwt.encode(claims, PRIVATE_PEM, algorithm="RS256", headers={"kid": KID})


def test_accepts_a_genuine_google_token():
    claims = verify_id_token(make_token(), PROJECT)
    assert claims["sub"] == "firebase-uid-123"
    assert claims["name"] == "Emin Baxishli"


def test_email_is_lowercased_so_accounts_cannot_fork_on_case():
    claims = verify_id_token(make_token(), PROJECT)
    assert claims["email"] == "emin@example.com"


def test_rejects_a_token_minted_for_another_firebase_project():
    token = make_token(
        aud="someone-elses-app", iss="https://securetoken.google.com/someone-elses-app"
    )
    with pytest.raises(GoogleIdentityError):
        verify_id_token(token, PROJECT)


def test_rejects_a_foreign_issuer_reusing_our_audience():
    with pytest.raises(GoogleIdentityError):
        verify_id_token(make_token(iss="https://accounts.google.com"), PROJECT)


def test_rejects_an_expired_token():
    now = int(time.time())
    with pytest.raises(GoogleIdentityError):
        verify_id_token(make_token(iat=now - 7200, exp=now - 3600), PROJECT)


def test_rejects_a_signature_from_an_unknown_key():
    other_private, _ = _keypair()
    now = int(time.time())
    token = jwt.encode(
        {
            "iss": f"https://securetoken.google.com/{PROJECT}",
            "aud": PROJECT,
            "sub": "uid",
            "iat": now - 30,
            "exp": now + 3600,
            "email": "a@b.c",
            "email_verified": True,
            "firebase": {"sign_in_provider": "google.com"},
        },
        other_private,
        algorithm="RS256",
        headers={"kid": KID},
    )
    with pytest.raises(GoogleIdentityError):
        verify_id_token(token, PROJECT)


def test_rejects_other_sign_in_providers_sharing_the_firebase_project():
    """The project has other apps and other sign-in methods enabled.

    Without this check an anonymous or password token from any of them would
    be a valid Muhai account.
    """
    for provider in ("anonymous", "password", "facebook.com", None):
        token = make_token(firebase={"sign_in_provider": provider})
        with pytest.raises(GoogleIdentityError):
            verify_id_token(token, PROJECT)


def test_rejects_a_token_with_no_subject():
    with pytest.raises(GoogleIdentityError):
        verify_id_token(make_token(sub=""), PROJECT)


def test_rejects_a_token_with_no_email():
    with pytest.raises(GoogleIdentityError):
        verify_id_token(make_token(email=""), PROJECT)


def test_rejects_an_unverified_email():
    with pytest.raises(GoogleIdentityError):
        verify_id_token(make_token(email_verified=False), PROJECT)


def test_rejects_an_unsigned_token():
    """`alg: none` is the classic JWT forgery and must never reach decode.

    Built by hand: python-jose refuses to *encode* an unsigned token, which is
    exactly why a forger would assemble one themselves.
    """
    def seg(obj):
        return base64.urlsafe_b64encode(json.dumps(obj).encode()).rstrip(b"=").decode()

    now = int(time.time())
    unsigned = "{}.{}.".format(
        seg({"alg": "none", "typ": "JWT", "kid": KID}),
        seg(
            {
                "iss": f"https://securetoken.google.com/{PROJECT}",
                "aud": PROJECT,
                "sub": "uid",
                "iat": now - 30,
                "exp": now + 3600,
                "email": "attacker@example.com",
                "email_verified": True,
                "firebase": {"sign_in_provider": "google.com"},
            }
        ),
    )
    with pytest.raises(GoogleIdentityError):
        verify_id_token(unsigned, PROJECT)


def test_rejects_garbage():
    for bad in ("", "not-a-jwt", "a.b.c"):
        with pytest.raises(GoogleIdentityError):
            verify_id_token(bad, PROJECT)


def test_is_off_when_no_project_is_configured():
    with pytest.raises(GoogleIdentityError):
        verify_id_token(make_token(), "")
