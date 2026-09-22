"""The company workspace — Muhai's system of record.

This replaces Cloud Firestore. The document shapes the web client works with
are preserved exactly (camelCase field names, ISO ``YYYY-MM-DD`` date strings),
so the browser code did not have to learn a new vocabulary when the store
changed; only the transport did.

Each table carries a typed column for every field the product actually reads —
the tax engine, the Muhai Score and the forecast all depend on them, and a
finance ledger has no business hiding money in a JSON blob — plus an ``extra``
JSONB column that round-trips any additional keys a document carries
(``vatRate``, ``notes``, …). Reads merge ``extra`` back in, so a document
written by the client comes back equivalent to what it sent.

Ownership is a single column: everything hangs off ``company_id``. That is the
same one-check rule the old Firestore security rules enforced, now expressed as
a WHERE clause the database itself backs with foreign keys.
"""
import datetime as dt
from typing import Any, List

from sqlalchemy import Boolean, Date, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, uuid_pk


def _extra() -> Mapped[dict[str, Any]]:
    """Catch-all for document keys without a column of their own."""
    return mapped_column(JSONB, default=dict, nullable=False)


def _company_fk() -> Mapped[str]:
    return mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True, nullable=False
    )


class Company(Base, TimestampMixin):
    """One company per account — the root every other row hangs from."""

    __tablename__ = "companies"

    id: Mapped[str] = uuid_pk()
    name: Mapped[str] = mapped_column(nullable=False)
    tax_id: Mapped[str] = mapped_column(String(32), default="", nullable=False)
    tax_office: Mapped[str] = mapped_column(default="", nullable=False)
    sector: Mapped[str] = mapped_column(default="general", nullable=False)
    city: Mapped[str] = mapped_column(default="", nullable=False)
    email: Mapped[str] = mapped_column(default="", nullable=False)
    legal_form: Mapped[str] = mapped_column(default="ltd", nullable=False)
    currency: Mapped[str] = mapped_column(String(8), default="TRY", nullable=False)
    # Opening cash. The dashboard adds the movement history to this.
    cash_balance: Mapped[float] = mapped_column(
        Numeric(16, 2), default=0, nullable=False
    )
    seeded: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    seeded_at: Mapped[str | None] = mapped_column(nullable=True)
    owner_user_id: Mapped[str | None] = mapped_column(String, nullable=True)
    extra: Mapped[dict[str, Any]] = _extra()

    members: Mapped[List["User"]] = relationship(  # noqa: F821
        back_populates="company", foreign_keys="User.company_id"
    )
    company_invoices: Mapped[List["CompanyInvoice"]] = relationship(
        back_populates="company", cascade="all, delete-orphan"
    )
    company_transactions: Mapped[List["CompanyTransaction"]] = relationship(
        back_populates="company", cascade="all, delete-orphan"
    )
    company_products: Mapped[List["CompanyProduct"]] = relationship(
        back_populates="company", cascade="all, delete-orphan"
    )
    company_employees: Mapped[List["CompanyEmployee"]] = relationship(
        back_populates="company", cascade="all, delete-orphan"
    )
    company_tax_obligations: Mapped[List["CompanyTaxObligation"]] = relationship(
        back_populates="company", cascade="all, delete-orphan"
    )
    company_vendor_categories: Mapped[List["CompanyVendorCategory"]] = relationship(
        back_populates="company", cascade="all, delete-orphan"
    )


class CompanyInvoice(Base, TimestampMixin):
    __tablename__ = "company_invoices"

    id: Mapped[str] = uuid_pk()
    company_id: Mapped[str] = _company_fk()

    number: Mapped[str] = mapped_column(default="", nullable=False)
    vendor: Mapped[str] = mapped_column(default="", nullable=False)
    tax_id: Mapped[str] = mapped_column(String(32), default="", nullable=False)
    # "sales" (money owed to us) or "purchase" (money we owe).
    direction: Mapped[str] = mapped_column(default="purchase", nullable=False)
    issue_date: Mapped[dt.date | None] = mapped_column(Date, index=True, nullable=True)
    due_date: Mapped[dt.date | None] = mapped_column(Date, nullable=True)
    paid_date: Mapped[dt.date | None] = mapped_column(Date, nullable=True)
    net_amount: Mapped[float] = mapped_column(Numeric(16, 2), default=0, nullable=False)
    vat_amount: Mapped[float] = mapped_column(Numeric(16, 2), default=0, nullable=False)
    amount: Mapped[float] = mapped_column(Numeric(16, 2), default=0, nullable=False)
    status: Mapped[str] = mapped_column(default="pending", nullable=False)
    category: Mapped[str] = mapped_column(default="other", nullable=False)
    # "manual" | "ocr" | "browser-ocr"
    source: Mapped[str] = mapped_column(default="manual", nullable=False)
    ocr_confidence: Mapped[float | None] = mapped_column(Numeric(5, 4), nullable=True)
    needs_review: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    demo: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    extra: Mapped[dict[str, Any]] = _extra()

    company: Mapped["Company"] = relationship(back_populates="company_invoices")


class CompanyTransaction(Base, TimestampMixin):
    __tablename__ = "company_transactions"

    id: Mapped[str] = uuid_pk()
    company_id: Mapped[str] = _company_fk()

    date: Mapped[dt.date | None] = mapped_column(Date, index=True, nullable=True)
    amount: Mapped[float] = mapped_column(Numeric(16, 2), default=0, nullable=False)
    # "income" or "expense". Amounts stay positive; the type carries the sign.
    type: Mapped[str] = mapped_column(default="expense", nullable=False)
    category: Mapped[str] = mapped_column(default="other", nullable=False)
    description: Mapped[str] = mapped_column(default="", nullable=False)
    vendor: Mapped[str] = mapped_column(default="", nullable=False)
    # Set when this movement was posted by settling an invoice.
    invoice_id: Mapped[str | None] = mapped_column(nullable=True)
    demo: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    extra: Mapped[dict[str, Any]] = _extra()

    company: Mapped["Company"] = relationship(back_populates="company_transactions")


class CompanyProduct(Base, TimestampMixin):
    __tablename__ = "company_products"

    id: Mapped[str] = uuid_pk()
    company_id: Mapped[str] = _company_fk()

    name: Mapped[str] = mapped_column(nullable=False)
    sku: Mapped[str] = mapped_column(default="", nullable=False)
    stock: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    min_stock: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    unit_price: Mapped[float] = mapped_column(Numeric(16, 2), default=0, nullable=False)
    monthly_usage: Mapped[float] = mapped_column(
        Numeric(16, 2), default=0, nullable=False
    )
    unit: Mapped[str] = mapped_column(default="adet", nullable=False)
    demo: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    extra: Mapped[dict[str, Any]] = _extra()

    company: Mapped["Company"] = relationship(back_populates="company_products")


class CompanyEmployee(Base, TimestampMixin):
    __tablename__ = "company_employees"

    id: Mapped[str] = uuid_pk()
    company_id: Mapped[str] = _company_fk()

    name: Mapped[str] = mapped_column(nullable=False)
    # Job title, not an access role — the access role lives on User.
    role: Mapped[str] = mapped_column(default="", nullable=False)
    gross_salary: Mapped[float] = mapped_column(
        Numeric(16, 2), default=0, nullable=False
    )
    start_date: Mapped[dt.date | None] = mapped_column(Date, nullable=True)
    sgk_no: Mapped[str] = mapped_column(String(32), default="", nullable=False)
    demo: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    extra: Mapped[dict[str, Any]] = _extra()

    company: Mapped["Company"] = relationship(back_populates="company_employees")


class CompanyTaxObligation(Base, TimestampMixin):
    __tablename__ = "company_tax_obligations"

    id: Mapped[str] = uuid_pk()
    company_id: Mapped[str] = _company_fk()

    type: Mapped[str] = mapped_column(default="kdv", nullable=False)
    name: Mapped[str] = mapped_column(default="", nullable=False)
    period: Mapped[str] = mapped_column(String(16), default="", nullable=False)
    due_date: Mapped[dt.date | None] = mapped_column(Date, index=True, nullable=True)
    amount: Mapped[float] = mapped_column(Numeric(16, 2), default=0, nullable=False)
    # "draft" | "filed" | "paid"
    status: Mapped[str] = mapped_column(default="draft", nullable=False)
    paid_date: Mapped[dt.date | None] = mapped_column(Date, nullable=True)
    demo: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    extra: Mapped[dict[str, Any]] = _extra()

    company: Mapped["Company"] = relationship(back_populates="company_tax_obligations")


class CompanyVendorCategory(Base, TimestampMixin):
    """What the classifier has learned about one vendor.

    The keyword rules in ``expense_classifier.py`` are a starting guess. When a
    user files "Teknopark Gayrimenkul" under rent rather than the ``other`` the
    rules produced, that correction is the company's own knowledge and belongs
    with its data — so it lives here rather than in the stateless compute
    layer, and the browser posts it back as part of the classify request.

    Deliberately *not* unique on (company_id, vendor_key): the workspace router
    is generic CRUD with no upsert, and a database conflict would surface as a
    500 in the middle of saving an invoice. The client reads the collection
    before it writes and patches the existing row; a duplicate that slips
    through is resolved on read by taking the newest.
    """

    __tablename__ = "company_vendor_categories"

    id: Mapped[str] = uuid_pk()
    company_id: Mapped[str] = _company_fk()

    # Normalised for lookup: casefolded, diacritics stripped, collapsed spaces.
    vendor_key: Mapped[str] = mapped_column(index=True, nullable=False)
    # The vendor as the user actually typed it, for display.
    vendor: Mapped[str] = mapped_column(default="", nullable=False)
    category: Mapped[str] = mapped_column(default="other", nullable=False)
    # True when a human overrode the suggestion, false when the app merely
    # cached what the rules already said.
    corrected: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    extra: Mapped[dict[str, Any]] = _extra()

    company: Mapped["Company"] = relationship(
        back_populates="company_vendor_categories"
    )
