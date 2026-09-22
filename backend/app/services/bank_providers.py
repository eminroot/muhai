"""Bank connection presets — what differs between one Turkish bank API and the next.

Every bank in Turkey publishes a different JSON shape behind a different
gateway, and the gateway hostnames, paths and scopes are handed out with the
credentials rather than published. So this module carries the part that *is*
stable — the authentication style, the header names, and the vocabulary each
bank uses for "date", "amount" and "description" — and leaves the endpoint
itself to configuration.

The consequence, which is the point of the design: connecting a real bank is
an ``.env`` change, not a code change. Set ``BANK_PROVIDER`` to a preset, paste
the base URL and credentials from the bank's developer portal, and the same
client, the same normaliser and the same reconciliation engine run unmodified.

A preset's ``base_url`` is deliberately empty until an operator fills it in. A
hostname written from memory would fail at the worst possible moment — with
real credentials in the file, in front of an audience.

Field lookup is tolerant rather than exact. ``FieldMap`` lists *candidate* keys
per field, matched case-insensitively and diacritic-folded, and the normaliser
also descends into nested objects. That is what makes an unfamiliar response
shape work on the first attempt instead of the third.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Literal

# How the caller proves who it is.
#   oauth2_client_credentials — the open-banking norm: POST id+secret to a
#                               token endpoint, put the bearer on every call.
#   static_bearer             — a long-lived token issued by the portal.
#   api_key_header            — a key in a header the bank names (often "apikey").
#   none                      — the built-in sample provider; no network at all.
AuthStyle = Literal[
    "oauth2_client_credentials", "static_bearer", "api_key_header", "none"
]


@dataclass(frozen=True)
class FieldMap:
    """Candidate JSON keys for each normalised field, best guess first.

    Covers three vocabularies at once: Turkish (``tutar``, ``açıklama``), ISO
    20022 as the regulated gateways use it (``bookingDate``,
    ``creditDebitIndicator``), and the plain English most portals fall back to.
    A bank that uses none of them is handled by ``BANK_FIELD_MAP`` in the
    environment rather than by editing this file.
    """

    date: tuple[str, ...] = (
        "transactionDate", "bookingDate", "valueDate", "date", "operationDate",
        "islemTarihi", "işlemTarihi", "tarih", "valorTarihi", "createDate",
    )
    description: tuple[str, ...] = (
        "description", "remittanceInformation", "explanation", "narrative",
        "aciklama", "açıklama", "islemAciklamasi", "işlemAçıklaması", "detail",
        "transactionDescription", "label",
    )
    amount: tuple[str, ...] = (
        "amount", "transactionAmount", "tutar", "islemTutari", "işlemTutarı",
        "value", "amountValue",
    )
    # Some statements split the sign across two columns instead of signing the
    # amount. When either is present it wins over ``amount``.
    debit: tuple[str, ...] = ("debitAmount", "borc", "borç", "borcTutari", "debit")
    credit: tuple[str, ...] = ("creditAmount", "alacak", "alacakTutari", "credit")
    # ...and others put it in a flag: "DBIT"/"CRDT", "B"/"A", "debit"/"credit".
    direction: tuple[str, ...] = (
        "creditDebitIndicator", "direction", "transactionType", "islemTuru",
        "işlemTürü", "borcAlacakKodu", "drCr", "type",
    )
    currency: tuple[str, ...] = ("currency", "currencyCode", "paraBirimi", "doviz")
    balance: tuple[str, ...] = ("balance", "runningBalance", "bakiye", "kalanBakiye")
    reference: tuple[str, ...] = (
        "referenceNumber", "transactionId", "endToEndId", "referansNo", "fisNo", "id",
    )
    counterparty: tuple[str, ...] = (
        "counterpartyName", "creditorName", "debtorName", "karsiTaraf",
        "karşıTaraf", "senderName", "receiverName", "unvan", "adSoyad",
    )
    # Accounts endpoint.
    account_id: tuple[str, ...] = (
        "accountId", "accountNumber", "iban", "hesapNo", "id",
    )
    account_name: tuple[str, ...] = (
        "accountName", "nickname", "hesapAdi", "hesapAdı", "unvan", "name",
    )
    account_iban: tuple[str, ...] = ("iban", "IBAN", "ibanNo")
    account_balance: tuple[str, ...] = (
        "availableBalance", "balance", "kullanilabilirBakiye", "bakiye",
    )

    def merged(self, overrides: dict[str, Any] | None) -> "FieldMap":
        """Apply ``BANK_FIELD_MAP``: the operator's keys are tried first.

        Additive on purpose. A bank that names one column oddly should not lose
        the defaults for the other eight.
        """
        if not overrides:
            return self
        patch: dict[str, tuple[str, ...]] = {}
        for name, value in overrides.items():
            if not hasattr(self, name):
                continue
            extra = (value,) if isinstance(value, str) else tuple(str(v) for v in value)
            current = getattr(self, name)
            patch[name] = extra + tuple(c for c in current if c not in extra)
        return replace(self, **patch)


@dataclass(frozen=True)
class BankProvider:
    """One bank's contract, as far as this client needs to know it."""

    key: str
    display_name: str
    auth: AuthStyle
    portal: str = ""  # where an operator gets the credentials
    base_url: str = ""
    token_url: str = ""  # relative to base_url, or absolute
    scope: str = ""
    accounts_path: str = "/accounts"
    # ``{account_id}`` is substituted. A bank that takes the account as a query
    # parameter instead says so in BANK_TRANSACTIONS_PATH.
    transactions_path: str = "/accounts/{account_id}/transactions"
    since_param: str = "startDate"
    until_param: str = "endDate"
    date_format: str = "%Y-%m-%d"
    api_key_header: str = "apikey"
    # Where the array hides in the response body. Tried in order; an empty
    # string means the body is itself the array.
    list_keys: tuple[str, ...] = (
        "", "data", "items", "transactions", "accounts", "result", "results",
        "data.transactions", "data.accounts", "data.items", "content",
        "hesapHareketleri", "hareketler", "hesaplar",
    )
    fields: FieldMap = FieldMap()
    notes: str = ""

    @property
    def needs_credentials(self) -> bool:
        return self.auth != "none"


# Presets. Each fixes the authentication style and the header the bank expects;
# the host, paths and scope arrive with the credentials. ``custom`` is the
# honest default — it assumes nothing and reads everything from the
# environment, and it is also what a bank not listed here should use.
_PRESETS: dict[str, BankProvider] = {
    "custom": BankProvider(
        key="custom",
        display_name="Özel / Custom",
        auth="oauth2_client_credentials",
        notes="Tüm ayarlar ortam değişkenlerinden okunur; listede olmayan banka için bunu kullanın.",
    ),
    "mock": BankProvider(
        key="mock",
        display_name="Örnek hesap (demo)",
        auth="none",
        notes="Ağ erişimi yok — akışı kimlik bilgisi olmadan göstermek için üretilen hareketler.",
    ),
    "garanti": BankProvider(
        key="garanti",
        display_name="Garanti BBVA",
        auth="oauth2_client_credentials",
        portal="https://developers.garantibbva.com.tr",
    ),
    "isbank": BankProvider(
        key="isbank",
        display_name="Türkiye İş Bankası",
        auth="oauth2_client_credentials",
        portal="https://apiportal.isbank.com.tr",
    ),
    "akbank": BankProvider(
        key="akbank",
        display_name="Akbank",
        auth="oauth2_client_credentials",
        portal="https://apiportal.akbank.com",
    ),
    "yapikredi": BankProvider(
        key="yapikredi",
        display_name="Yapı Kredi",
        auth="oauth2_client_credentials",
        portal="https://apiportal.yapikredi.com.tr",
    ),
    "qnb": BankProvider(
        key="qnb",
        display_name="QNB",
        auth="oauth2_client_credentials",
        portal="https://apiportal.qnb.com.tr",
    ),
    "denizbank": BankProvider(
        key="denizbank",
        display_name="DenizBank",
        auth="api_key_header",
        portal="https://apiportal.denizbank.com",
    ),
    "kuveytturk": BankProvider(
        key="kuveytturk",
        display_name="Kuveyt Türk",
        auth="oauth2_client_credentials",
        portal="https://developer.kuveytturk.com.tr",
    ),
    "vakifbank": BankProvider(
        key="vakifbank",
        display_name="VakıfBank",
        auth="oauth2_client_credentials",
        portal="https://developer.vakifbank.com.tr",
    ),
    "ziraat": BankProvider(
        key="ziraat",
        display_name="Ziraat Bankası",
        auth="oauth2_client_credentials",
        portal="https://apigw.ziraatbank.com.tr",
    ),
}


def provider_keys() -> list[str]:
    return list(_PRESETS)


def presets() -> list[BankProvider]:
    return list(_PRESETS.values())


def get_preset(key: str | None) -> BankProvider:
    """A preset by name, falling back to ``custom`` for an unknown one.

    Unknown names fall back rather than raise: a typo in .env should leave the
    bank page saying "not configured", not take the whole API down at import.
    """
    return _PRESETS.get((key or "custom").strip().lower(), _PRESETS["custom"])


def resolve_provider(cfg: Any) -> BankProvider:
    """Preset + environment overrides = the connection this deployment uses."""
    import json

    preset = get_preset(getattr(cfg, "BANK_PROVIDER", ""))

    overrides: dict[str, Any] = {}
    for env_name, attr in (
        ("BANK_API_BASE_URL", "base_url"),
        ("BANK_TOKEN_URL", "token_url"),
        ("BANK_SCOPE", "scope"),
        ("BANK_ACCOUNTS_PATH", "accounts_path"),
        ("BANK_TRANSACTIONS_PATH", "transactions_path"),
        ("BANK_SINCE_PARAM", "since_param"),
        ("BANK_UNTIL_PARAM", "until_param"),
        ("BANK_DATE_FORMAT", "date_format"),
        ("BANK_API_KEY_HEADER", "api_key_header"),
    ):
        value = (getattr(cfg, env_name, "") or "").strip()
        if value:
            overrides[attr] = value

    auth = (getattr(cfg, "BANK_AUTH_STYLE", "") or "").strip()
    if auth in ("oauth2_client_credentials", "static_bearer", "api_key_header", "none"):
        overrides["auth"] = auth

    raw_map = (getattr(cfg, "BANK_FIELD_MAP", "") or "").strip()
    if raw_map:
        try:
            overrides["fields"] = preset.fields.merged(json.loads(raw_map))
        except (ValueError, TypeError):
            # A malformed map is an operator typo. Ignore it and keep the
            # defaults — refusing to start would be the worse trade.
            pass

    if "base_url" in overrides:
        overrides["base_url"] = overrides["base_url"].rstrip("/")

    return replace(preset, **overrides) if overrides else preset
