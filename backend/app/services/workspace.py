"""Document ⇄ row mapping for the company workspace.

The web client speaks documents: camelCase keys, ISO ``YYYY-MM-DD`` date
strings, and whatever extra keys a given screen happens to carry. Postgres
speaks rows. This module is the only place that knows both, so the router
below it stays a thin generic CRUD surface and the frontend keeps the exact
vocabulary it already had.

Two rules make the round trip safe:

* Every known field has a typed column and a declared coercion. A string that
  cannot be read as a number becomes the column default rather than blowing up
  a bulk insert of four hundred seeded rows.
* Anything else is preserved verbatim in the ``extra`` JSONB column and merged
  back on read, so an unrecognised key is never silently dropped.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Callable

from app.db.models.company import (
    Company,
    CompanyEmployee,
    CompanyInvoice,
    CompanyProduct,
    CompanyTaxObligation,
    CompanyTransaction,
    CompanyVendorCategory,
)

# ── Coercions ─────────────────────────────────────────────────────────


def _as_str(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def _as_opt_str(value: Any) -> str | None:
    if value is None or value == "":
        return None
    return str(value)


def _as_float(value: Any) -> float:
    if isinstance(value, bool) or value is None or value == "":
        return 0.0
    try:
        return float(Decimal(str(value)))
    except (InvalidOperation, ValueError):
        return 0.0


def _as_opt_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(Decimal(str(value)))
    except (InvalidOperation, ValueError):
        return None


def _as_int(value: Any) -> int:
    if isinstance(value, bool) or value is None or value == "":
        return 0
    try:
        return int(float(Decimal(str(value))))
    except (InvalidOperation, ValueError):
        return 0


def _as_bool(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _as_date(value: Any) -> dt.date | None:
    """Parse an ISO calendar date. Timestamps are truncated to their date."""
    if value is None or value == "":
        return None
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    text = str(value).strip()
    try:
        return dt.date.fromisoformat(text[:10])
    except ValueError:
        return None


# ── Field maps ────────────────────────────────────────────────────────

Coercion = Callable[[Any], Any]


@dataclass(frozen=True)
class Collection:
    """One workspace collection: its table, its fields, its default order."""

    name: str
    model: type
    # document key -> (column name, coercion)
    fields: dict[str, tuple[str, Coercion]]
    order_by: str | None = None

    @property
    def columns(self) -> dict[str, str]:
        return {doc: column for doc, (column, _) in self.fields.items()}


COMPANY_FIELDS: dict[str, tuple[str, Coercion]] = {
    "name": ("name", _as_str),
    "taxId": ("tax_id", _as_str),
    "taxOffice": ("tax_office", _as_str),
    "sector": ("sector", _as_str),
    "city": ("city", _as_str),
    "email": ("email", _as_str),
    "legalForm": ("legal_form", _as_str),
    "currency": ("currency", _as_str),
    "cashBalance": ("cash_balance", _as_float),
    "seeded": ("seeded", _as_bool),
    "seededAt": ("seeded_at", _as_opt_str),
}

COMPANY = Collection(name="company", model=Company, fields=COMPANY_FIELDS)

COLLECTIONS: dict[str, Collection] = {
    "invoices": Collection(
        name="invoices",
        model=CompanyInvoice,
        order_by="issue_date",
        fields={
            "number": ("number", _as_str),
            "vendor": ("vendor", _as_str),
            "taxId": ("tax_id", _as_str),
            "direction": ("direction", _as_str),
            "issueDate": ("issue_date", _as_date),
            "dueDate": ("due_date", _as_date),
            "paidDate": ("paid_date", _as_date),
            "netAmount": ("net_amount", _as_float),
            "vatAmount": ("vat_amount", _as_float),
            "amount": ("amount", _as_float),
            "status": ("status", _as_str),
            "category": ("category", _as_str),
            "source": ("source", _as_str),
            "ocrConfidence": ("ocr_confidence", _as_opt_float),
            "needsReview": ("needs_review", _as_bool),
            "notes": ("notes", _as_opt_str),
            "demo": ("demo", _as_bool),
        },
    ),
    "transactions": Collection(
        name="transactions",
        model=CompanyTransaction,
        order_by="date",
        fields={
            "date": ("date", _as_date),
            "amount": ("amount", _as_float),
            "type": ("type", _as_str),
            "category": ("category", _as_str),
            "description": ("description", _as_str),
            "vendor": ("vendor", _as_str),
            "invoiceId": ("invoice_id", _as_opt_str),
            "demo": ("demo", _as_bool),
        },
    ),
    "products": Collection(
        name="products",
        model=CompanyProduct,
        fields={
            "name": ("name", _as_str),
            "sku": ("sku", _as_str),
            "stock": ("stock", _as_int),
            "minStock": ("min_stock", _as_int),
            "unitPrice": ("unit_price", _as_float),
            "monthlyUsage": ("monthly_usage", _as_float),
            "unit": ("unit", _as_str),
            "demo": ("demo", _as_bool),
        },
    ),
    "employees": Collection(
        name="employees",
        model=CompanyEmployee,
        fields={
            "name": ("name", _as_str),
            "role": ("role", _as_str),
            "grossSalary": ("gross_salary", _as_float),
            "startDate": ("start_date", _as_date),
            "sgkNo": ("sgk_no", _as_str),
            "demo": ("demo", _as_bool),
        },
    ),
    "vendorCategories": Collection(
        name="vendorCategories",
        model=CompanyVendorCategory,
        fields={
            "vendorKey": ("vendor_key", _as_str),
            "vendor": ("vendor", _as_str),
            "category": ("category", _as_str),
            "corrected": ("corrected", _as_bool),
        },
    ),
    "taxObligations": Collection(
        name="taxObligations",
        model=CompanyTaxObligation,
        order_by="due_date",
        fields={
            "type": ("type", _as_str),
            "name": ("name", _as_str),
            "period": ("period", _as_str),
            "dueDate": ("due_date", _as_date),
            "amount": ("amount", _as_float),
            "status": ("status", _as_str),
            "paidDate": ("paid_date", _as_date),
            "demo": ("demo", _as_bool),
        },
    ),
}

COLLECTION_NAMES = tuple(COLLECTIONS)

# Keys the client may send that are managed by the server, not the document.
RESERVED_KEYS = frozenset({"id", "createdAt", "companyId", "ownerUid", "members"})


# ── Document → row ────────────────────────────────────────────────────


def to_columns(spec: Collection, document: dict[str, Any]) -> dict[str, Any]:
    """Split a document into typed column values plus an ``extra`` remainder.

    Only keys actually present are returned, so this serves a PATCH as well as
    a create — an absent key means "leave it alone", not "set it to the
    default".
    """
    values: dict[str, Any] = {}
    extra: dict[str, Any] = {}

    for key, value in document.items():
        if key in RESERVED_KEYS:
            continue
        mapping = spec.fields.get(key)
        if mapping is None:
            extra[key] = value
            continue
        column, coerce = mapping
        values[column] = coerce(value)

    if extra:
        values["extra"] = extra
    return values


def apply_patch(spec: Collection, row: Any, document: dict[str, Any]) -> None:
    """Merge a partial document into an existing row.

    ``extra`` is merged rather than replaced: patching one unknown key must not
    erase the others already stored alongside it.
    """
    values = to_columns(spec, document)
    incoming_extra = values.pop("extra", None)

    for column, value in values.items():
        setattr(row, column, value)

    if incoming_extra:
        merged = dict(row.extra or {})
        merged.update(incoming_extra)
        row.extra = merged


# ── Row → document ────────────────────────────────────────────────────


def _json_safe(value: Any) -> Any:
    if isinstance(value, dt.datetime):
        return value.isoformat()
    if isinstance(value, dt.date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    return value


def to_document(spec: Collection, row: Any) -> dict[str, Any]:
    """Rebuild the document the client originally wrote."""
    document: dict[str, Any] = {"id": row.id}
    for key, (column, _) in spec.fields.items():
        document[key] = _json_safe(getattr(row, column))
    for key, value in (row.extra or {}).items():
        document.setdefault(key, value)
    created = getattr(row, "created_at", None)
    if created is not None:
        document["createdAt"] = _json_safe(created)
    return document


def company_document(company: Company) -> dict[str, Any]:
    document = to_document(COMPANY, company)
    document["ownerUid"] = company.owner_user_id
    return document
