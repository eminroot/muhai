"""Bank statements: normalise, categorise, reconcile.

Everything in this module is a pure function. Two sources feed it — a live
bank API response (``normalize_records``) and an uploaded CSV
(``parse_bank_csv``) — and both land in the same ``BankTxn``, so the
reconciliation engine, the categoriser and the UI never learn which one they
are looking at. A company without API access loses the fetch, not the feature.

The matcher answers the only question a business owner actually has about a
statement: *which of these movements is already in my books, and which is
not?* An unmatched row is the interesting one — it is either a missing invoice
or a payment nobody recorded.

Recovered from commit 5cb59c0, where it was deleted with the legacy API, and
extended: signed amounts, debit/credit columns, direction-aware matching and
globally-best assignment rather than first-come-first-served.
"""
from __future__ import annotations

import csv
import io
import re
import unicodedata
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from typing import Any, Iterable, Sequence

from app.services.bank_providers import FieldMap
from app.services.expense_classifier import CATEGORIES, classify_expense, vendor_key

# ── Text and number helpers ───────────────────────────────────────────

_FOLD = str.maketrans(
    {
        "ı": "i", "İ": "i", "ş": "s", "Ş": "s", "ğ": "g", "Ğ": "g",
        "ü": "u", "Ü": "u", "ö": "o", "Ö": "o", "ç": "c", "Ç": "c",
        "â": "a", "î": "i", "û": "u",
    }
)


def _fold(text: str) -> str:
    """Lowercase, strip Turkish diacritics, drop separators.

    Applied to both sides of every key comparison, so ``islemTarihi``,
    ``işlem_tarihi`` and ``İŞLEM TARİHİ`` are one key. Bank payloads disagree
    about all three of those things and about nothing else.
    """
    folded = unicodedata.normalize("NFC", text).translate(_FOLD).lower()
    return re.sub(r"[\s_\-.]", "", folded)


_AMOUNT_CLEAN_RE = re.compile(r"[^\d,.\-+]")
_DATE_FORMATS = (
    "%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d", "%Y%m%d",
    "%d.%m.%y", "%m/%d/%Y",
)


def parse_amount(raw: Any) -> float | None:
    """Read a money value written any of the ways a bank writes one.

    Turkish formatting (``1.234,56``) and English (``1,234.56``) are told apart
    by which separator comes last, because that one is always the decimal
    point. A trailing ``-`` is Turkish statement convention for a debit.
    """
    if isinstance(raw, bool):
        return None
    if isinstance(raw, (int, float)):
        return round(float(raw), 2)

    text = str(raw or "").strip()
    if not text:
        return None

    trailing_negative = text.endswith("-")
    cleaned = _AMOUNT_CLEAN_RE.sub("", text).strip()
    if not cleaned:
        return None

    negative = cleaned.startswith("-") or trailing_negative
    cleaned = cleaned.lstrip("+-").rstrip("-")

    if "," in cleaned and "." in cleaned:
        decimal_sep = "," if cleaned.rfind(",") > cleaned.rfind(".") else "."
        thousands_sep = "." if decimal_sep == "," else ","
        cleaned = cleaned.replace(thousands_sep, "").replace(decimal_sep, ".")
    elif "," in cleaned:
        # A lone comma is a decimal comma unless it groups thousands exactly.
        head, _, tail = cleaned.rpartition(",")
        cleaned = f"{head.replace(',', '')}.{tail}" if len(tail) != 3 or not head else cleaned.replace(",", "")
    elif "." in cleaned:
        # Symmetrically: a lone dot with exactly three digits after it is a
        # Turkish thousands separator ("1.500" is fifteen hundred lira), and
        # more than one dot always is.
        head, _, tail = cleaned.rpartition(".")
        if cleaned.count(".") > 1 or (len(tail) == 3 and head):
            cleaned = cleaned.replace(".", "")

    try:
        value = round(float(cleaned), 2)
    except ValueError:
        return None
    return -value if negative and value > 0 else value


def parse_date(raw: Any) -> date | None:
    """Read a calendar date, including ISO timestamps with an offset."""
    if isinstance(raw, datetime):
        return raw.date()
    if isinstance(raw, date):
        return raw

    text = str(raw or "").strip()
    if not text:
        return None
    if text.isdigit() and len(text) == 13:  # epoch milliseconds
        try:
            return datetime.fromtimestamp(int(text) / 1000).date()
        except (OverflowError, OSError, ValueError):
            return None

    head = text.replace("Z", "").split("+")[0].strip()
    try:
        return datetime.fromisoformat(head).date()
    except ValueError:
        pass
    # Timestamps whose date part is not ISO ("05.09.2026 14:31") — take the
    # first token, which is the calendar date in every format banks emit.
    first = head.split("T")[0].split(" ")[0]
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(first, fmt).date()
        except ValueError:
            continue
    return None


# ── Tolerant field lookup ─────────────────────────────────────────────

_DEBIT_WORDS = {"dbit", "debit", "b", "borc", "d", "cikis", "odeme", "out", "gidenfast"}
_CREDIT_WORDS = {"crdt", "credit", "a", "alacak", "c", "giris", "tahsilat", "in", "gelenfast"}


def pick(record: Any, candidates: Sequence[str], *, depth: int = 2) -> Any:
    """First non-empty value among ``candidates``, searched tolerantly.

    Keys are compared folded, a dotted candidate walks nested objects, and
    anything not found at the top level is looked for one level down. Bank
    payloads nest constantly — ``{"amount": {"value": 120, "currency": "TRY"}}``
    is as common as a flat field — and an exact-match lookup would return
    nothing for half of them.
    """
    if not isinstance(record, dict):
        return None

    folded = {_fold(str(k)): v for k, v in record.items()}

    for candidate in candidates:
        if "." in candidate:
            cursor: Any = record
            for part in candidate.split("."):
                if not isinstance(cursor, dict):
                    cursor = None
                    break
                cursor = {_fold(str(k)): v for k, v in cursor.items()}.get(_fold(part))
            if cursor not in (None, "", [], {}):
                return cursor
            continue

        value = folded.get(_fold(candidate))
        if isinstance(value, dict):
            # ISO 20022 style: {"amount": {"value": …}} / {"amount": {"amount": …}}
            inner = pick(value, ("value", "amount", "content", "text"), depth=0)
            if inner not in (None, "", [], {}):
                return inner
        elif value not in (None, "", [], {}):
            return value

    if depth > 0:
        for value in record.values():
            if isinstance(value, dict):
                found = pick(value, candidates, depth=depth - 1)
                if found not in (None, "", [], {}):
                    return found
    return None


def extract_list(body: Any, list_keys: Sequence[str]) -> list[dict]:
    """Find the array of records in a response body.

    Banks wrap their payloads differently and some wrap them twice. Rather
    than one path per bank, try the known shapes and then fall back to the
    first list of objects anywhere in the body.
    """
    if isinstance(body, list):
        return [r for r in body if isinstance(r, dict)]
    if not isinstance(body, dict):
        return []

    for key in list_keys:
        if not key:
            continue
        cursor: Any = body
        for part in key.split("."):
            if not isinstance(cursor, dict):
                cursor = None
                break
            cursor = {_fold(str(k)): v for k, v in cursor.items()}.get(_fold(part))
        if isinstance(cursor, list):
            return [r for r in cursor if isinstance(r, dict)]

    for value in body.values():
        if isinstance(value, list) and value and isinstance(value[0], dict):
            return [r for r in value if isinstance(r, dict)]
        if isinstance(value, dict):
            nested = extract_list(value, list_keys)
            if nested:
                return nested
    return []


# ── The normalised row ────────────────────────────────────────────────


@dataclass
class BankTxn:
    """One statement line, whatever produced it.

    ``amount`` is signed: money in is positive, money out negative. That is the
    one convention the rest of the pipeline relies on — the ledger entry, the
    matcher and the UI all read the sign rather than a separate flag.
    """

    date: date | None
    description: str
    amount: float
    currency: str = "TRY"
    balance: float | None = None
    reference: str | None = None
    counterparty: str | None = None
    category: str = "other"
    source: str = "api"  # "api" | "csv"

    @property
    def direction(self) -> str:
        return "in" if self.amount >= 0 else "out"

    @property
    def vendor(self) -> str:
        """Best available counterparty name, falling back to the description."""
        return (self.counterparty or self.description or "").strip()

    def as_document(self) -> dict[str, Any]:
        doc = asdict(self)
        doc["date"] = self.date.isoformat() if self.date else None
        doc["direction"] = self.direction
        doc["vendor"] = self.vendor
        return doc


def _signed_amount(record: Any, fields: FieldMap) -> float | None:
    """Resolve the signed amount from whichever convention the bank used."""
    debit = parse_amount(pick(record, fields.debit))
    credit = parse_amount(pick(record, fields.credit))
    if debit or credit:
        return round((credit or 0.0) - abs(debit or 0.0), 2)

    amount = parse_amount(pick(record, fields.amount))
    if amount is None:
        return None

    flag = pick(record, fields.direction)
    if flag is not None:
        folded = _fold(str(flag))
        if folded in _DEBIT_WORDS or folded.startswith(("dbit", "debit", "borc")):
            return -abs(amount)
        if folded in _CREDIT_WORDS or folded.startswith(("crdt", "credit", "alacak")):
            return abs(amount)
    return amount


def normalize_records(
    records: Iterable[Any],
    fields: FieldMap | None = None,
    *,
    source: str = "api",
) -> list[BankTxn]:
    """Bank JSON records -> ``BankTxn``. Rows without an amount are dropped."""
    fields = fields or FieldMap()
    rows: list[BankTxn] = []

    for record in records:
        if not isinstance(record, dict):
            continue
        amount = _signed_amount(record, fields)
        if amount is None:
            continue

        counterparty = pick(record, fields.counterparty)
        reference = pick(record, fields.reference)
        rows.append(
            BankTxn(
                date=parse_date(pick(record, fields.date)),
                description=str(pick(record, fields.description) or "").strip(),
                amount=amount,
                currency=str(pick(record, fields.currency) or "TRY").upper()[:3],
                balance=parse_amount(pick(record, fields.balance)),
                reference=str(reference) if reference else None,
                counterparty=str(counterparty).strip() if counterparty else None,
                source=source,
            )
        )
    return rows


def normalize_accounts(records: Iterable[Any], fields: FieldMap | None = None) -> list[dict]:
    """Bank JSON accounts -> the shape the account picker needs."""
    fields = fields or FieldMap()
    accounts: list[dict] = []
    for record in records:
        if not isinstance(record, dict):
            continue
        identifier = pick(record, fields.account_id)
        if identifier in (None, ""):
            continue
        iban = pick(record, fields.account_iban)
        accounts.append(
            {
                "id": str(identifier),
                "name": str(pick(record, fields.account_name) or "") or str(identifier),
                "iban": str(iban) if iban else None,
                "currency": str(pick(record, fields.currency) or "TRY").upper()[:3],
                "balance": parse_amount(pick(record, fields.account_balance)),
            }
        )
    return accounts


# ── CSV import (the path that needs no bank API at all) ───────────────

_CSV_DATE_KEYS = ("tarih", "date", "islemtarihi", "valortarihi", "bookingdate")
_CSV_DESC_KEYS = ("aciklama", "description", "islem", "detay", "explanation", "narrative")
_CSV_AMOUNT_KEYS = ("tutar", "amount", "miktar", "islemtutari")
_CSV_DEBIT_KEYS = ("borc", "debit", "cikis", "odeme")
_CSV_CREDIT_KEYS = ("alacak", "credit", "giris", "tahsilat")
_CSV_BALANCE_KEYS = ("bakiye", "balance", "kalanbakiye")
_CSV_PARTY_KEYS = ("karsitaraf", "unvan", "gonderen", "alici", "counterparty", "adsoyad")


def _header_for(headers: list[str], candidates: tuple[str, ...]) -> str | None:
    """Match a column by folded substring — headers carry stray spaces and units."""
    folded = [(_fold(h), h) for h in headers]
    for candidate in candidates:
        for folded_header, original in folded:
            if candidate in folded_header:
                return original
    return None


def parse_bank_csv(content: str) -> list[BankTxn]:
    """Parse a bank statement CSV/TSV exported from internet banking.

    Delimiter and column names are detected rather than configured: the
    business owner exporting the file has no idea which of the three formats
    their bank used, and should not have to.
    """
    if not content:
        return []
    content = content.lstrip("﻿")

    sample = content[:4096]
    delimiter = ";" if sample.count(";") > sample.count(",") else ","
    if sample.count("\t") > sample.count(delimiter):
        delimiter = "\t"

    reader = csv.DictReader(io.StringIO(content), delimiter=delimiter)
    if not reader.fieldnames:
        return []

    headers = [h for h in reader.fieldnames if h]
    date_key = _header_for(headers, _CSV_DATE_KEYS)
    desc_key = _header_for(headers, _CSV_DESC_KEYS)
    amount_key = _header_for(headers, _CSV_AMOUNT_KEYS)
    debit_key = _header_for(headers, _CSV_DEBIT_KEYS)
    credit_key = _header_for(headers, _CSV_CREDIT_KEYS)
    balance_key = _header_for(headers, _CSV_BALANCE_KEYS)
    party_key = _header_for(headers, _CSV_PARTY_KEYS)

    rows: list[BankTxn] = []
    for raw in reader:
        debit = parse_amount(raw.get(debit_key)) if debit_key else None
        credit = parse_amount(raw.get(credit_key)) if credit_key else None
        if debit or credit:
            amount = round((credit or 0.0) - abs(debit or 0.0), 2)
        else:
            amount = parse_amount(raw.get(amount_key)) if amount_key else None
        if amount is None:
            continue

        counterparty = (raw.get(party_key) or "").strip() if party_key else ""
        rows.append(
            BankTxn(
                date=parse_date(raw.get(date_key)) if date_key else None,
                description=(raw.get(desc_key) or "").strip() if desc_key else "",
                amount=amount,
                balance=parse_amount(raw.get(balance_key)) if balance_key else None,
                counterparty=counterparty or None,
                source="csv",
            )
        )
    return rows


# ── Categorisation ────────────────────────────────────────────────────

# Movements that are about the bank itself, not about a purchase. The general
# expense keywords would file most of these under "bank_fees" anyway, but a
# transfer is not a fee and a tax payment is not a transfer.
_BANK_RULES: list[tuple[str, tuple[str, ...]]] = [
    ("tax_payments", ("vergi", "kdv", "sgk", "muhtasar", "gib", "stopaj", "damga")),
    ("payroll", ("maas", "bordro", "personel odeme", "ucret odemesi")),
    ("bank_fees", ("komisyon", "masraf", "bsmv", "hesap isletim", "kart aidat", "faiz")),
]

# How the money moved, which is not what it was spent on. Statement lines lead
# with these, and leaving them in makes the expense classifier read every
# supplier payment as a bank fee — "EFT GIDEN - EGE AMBALAJ" is not a fee.
_TRANSFER_NOISE = re.compile(
    r"\b(fast|eft|havale|virman|transfer|swift|gelen|giden|odeme|odemesi)\b"
)


def categorise(row: BankTxn, learned: dict[str, str] | None = None) -> str:
    """Category for one movement: what the company taught us, then the rules.

    Same precedence as ``/api/compute/classify`` — a correction the user made
    about a vendor beats any keyword table, because it is a fact about this
    company rather than a guess about Turkish business vocabulary.
    """
    if row.amount > 0:
        return "other"  # income is not an expense category

    if learned:
        remembered = learned.get(vendor_key(row.vendor))
        if remembered in CATEGORIES:
            return remembered

    # _fold() removes separators, so match the bank rules against a spaced
    # fold instead — "hesap isletim" has to survive as two words.
    text = f"{row.description} {row.counterparty or ''}".lower().translate(_FOLD)
    for category, keywords in _BANK_RULES:
        if any(k in text for k in keywords):
            return category

    return classify_expense(_TRANSFER_NOISE.sub(" ", text), row.counterparty)


def categorise_all(rows: Iterable[BankTxn], learned: dict[str, str] | None = None) -> list[BankTxn]:
    normalised = {vendor_key(k): v for k, v in (learned or {}).items()}
    for row in rows:
        row.category = categorise(row, normalised)
    return list(rows)


# ── Reconciliation ────────────────────────────────────────────────────


@dataclass(frozen=True)
class InvoiceRef:
    """The slice of an invoice the matcher needs."""

    id: str
    amount: float
    date: date | None = None
    vendor: str | None = None
    number: str | None = None
    direction: str = "purchase"  # "purchase" (money out) | "sales" (money in)
    status: str = "pending"


@dataclass
class Match:
    row_index: int
    invoice_id: str | None
    status: str  # "matched" | "unmatched"
    confidence: float = 0.0
    reasons: list[str] = field(default_factory=list)


def _amounts_close(a: float, b: float, tol_pct: float) -> bool:
    if b == 0:
        return abs(a) < 0.01
    # A floor of one lira keeps rounding on small amounts from failing a match
    # that is obviously the same payment.
    tolerance = max(abs(b) * tol_pct, 1.0)
    return abs(abs(a) - abs(b)) <= tolerance


def _name_similarity(a: str | None, b: str | None) -> float:
    """Token overlap on folded names. Bank descriptions bury the vendor in
    boilerplate ("FAST GELEN - ACME LTD STI - FATURA"), so containment counts
    as a full hit and the rest is Jaccard."""
    if not a or not b:
        return 0.0
    at, bt = _fold(a), _fold(b)
    if not at or not bt:
        return 0.0
    if at in bt or bt in at:
        return 1.0
    a_tokens = {t for t in re.split(r"\W+", a.lower()) if len(t) > 2}
    b_tokens = {t for t in re.split(r"\W+", b.lower()) if len(t) > 2}
    a_tokens = {_fold(t) for t in a_tokens}
    b_tokens = {_fold(t) for t in b_tokens}
    if not a_tokens or not b_tokens:
        return 0.0
    return len(a_tokens & b_tokens) / len(a_tokens | b_tokens)


def _direction_fits(row: BankTxn, invoice: InvoiceRef) -> bool:
    """Money out settles a purchase; money in settles a sale."""
    return (invoice.direction == "sales") == (row.amount >= 0)


def reconcile(
    rows: Sequence[BankTxn],
    invoices: Sequence[InvoiceRef],
    *,
    date_window_days: int = 7,
    amount_tol_pct: float = 0.01,
    min_confidence: float = 0.6,
) -> list[Match]:
    """Pair statement lines with invoices, best pair first.

    Globally greedy rather than row-by-row: every candidate pair is scored,
    then assignments are taken in descending confidence. Two invoices for the
    same amount in the same week would otherwise be matched by whichever row
    happened to be read first, which is not a decision the file order should
    be making.
    """
    candidates: list[tuple[float, int, str, list[str]]] = []

    for index, row in enumerate(rows):
        for invoice in invoices:
            if not _direction_fits(row, invoice):
                continue
            if not _amounts_close(row.amount, invoice.amount, amount_tol_pct):
                continue

            reasons = ["amount"]
            score = 0.55

            if row.date and invoice.date:
                gap = abs((row.date - invoice.date).days)
                if gap > date_window_days:
                    continue
                score += 0.2 * (1 - gap / max(date_window_days, 1))
                reasons.append("date")

            name = _name_similarity(row.vendor, invoice.vendor)
            if name:
                score += 0.2 * name
                reasons.append("vendor")

            if invoice.number and _fold(invoice.number) in _fold(row.description):
                score += 0.15
                reasons.append("invoice_no")

            candidates.append((round(min(score, 1.0), 2), index, invoice.id, reasons))

    candidates.sort(key=lambda c: (-c[0], c[1]))

    taken_rows: set[int] = set()
    taken_invoices: set[str] = set()
    matched: dict[int, tuple[str, float, list[str]]] = {}

    for score, index, invoice_id, reasons in candidates:
        if score < min_confidence or index in taken_rows or invoice_id in taken_invoices:
            continue
        taken_rows.add(index)
        taken_invoices.add(invoice_id)
        matched[index] = (invoice_id, score, reasons)

    results: list[Match] = []
    for index in range(len(rows)):
        if index in matched:
            invoice_id, score, reasons = matched[index]
            results.append(Match(index, invoice_id, "matched", score, reasons))
        else:
            results.append(Match(index, None, "unmatched", 0.0, []))
    return results


def summarise(rows: Sequence[BankTxn], matches: Sequence[Match]) -> dict[str, float]:
    matched = sum(1 for m in matches if m.status == "matched")
    money_in = round(sum(r.amount for r in rows if r.amount > 0), 2)
    money_out = round(sum(-r.amount for r in rows if r.amount < 0), 2)
    return {
        "total": len(rows),
        "matched": matched,
        "unmatched": len(rows) - matched,
        "match_rate": round(matched / len(rows), 3) if rows else 0.0,
        "money_in": money_in,
        "money_out": money_out,
        "net": round(money_in - money_out, 2),
    }


def to_transaction_document(row: BankTxn) -> dict[str, Any]:
    """A workspace ``transactions`` document for an unmatched movement.

    The bank row is evidence that money moved; the ledger entry is the record
    of it. Written through ``/api/workspace`` like any other document — this
    module never touches a table.
    """
    return {
        "date": row.date.isoformat() if row.date else None,
        "amount": round(abs(row.amount), 2),
        "type": "income" if row.amount >= 0 else "expense",
        "category": row.category or "other",
        "description": row.description or (row.counterparty or "Banka hareketi"),
        "vendor": row.counterparty or "",
        "source": "bank",
    }
