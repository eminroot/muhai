"""Aggregates all ORM models so importing this package registers them on
``Base.metadata`` (used by Alembic autogenerate). Kept separate from
``app.db.base`` to avoid a circular import between base and the models.

``Company`` and the ``Company*`` tables are the system of record; ``User`` is
the account that signs in to one. The older user-scoped tables (``Invoice``,
``Transaction``, …) and the ``/api/invoices``-style routes above them were
deleted on 2026-09-13 -- nothing had called them since the workspace landed.
"""
from app.db.models.company import (
    Company,
    CompanyEmployee,
    CompanyInvoice,
    CompanyProduct,
    CompanyTaxObligation,
    CompanyTransaction,
    CompanyVendorCategory,
)
from app.db.models.user import User

__all__ = [
    "Company",
    "CompanyInvoice",
    "CompanyTransaction",
    "CompanyProduct",
    "CompanyEmployee",
    "CompanyTaxObligation",
    "CompanyVendorCategory",
    "User",
]
