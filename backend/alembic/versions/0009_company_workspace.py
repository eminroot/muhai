"""company workspace — the tables that replaced Cloud Firestore

Creates the company root plus the five collections the web client reads and
writes (invoices, transactions, products, employees, tax obligations), and
links each user account to its company.

The older user-scoped tables from 0001-0008 are left untouched: they back the
deprecated ``/api/invoices``-style routes, which no longer have a caller but
still work.

Revision ID: 0009_company_workspace
Revises: 0008_vendor_categories
Create Date: 2026-09-08 00:00:00

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0009_company_workspace"
down_revision: Union[str, None] = "0008_vendor_categories"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _uuid_pk() -> sa.Column:
    return sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False)


def _company_fk() -> sa.Column:
    return sa.Column("company_id", postgresql.UUID(as_uuid=False), nullable=False)


def _created_at() -> sa.Column:
    return sa.Column(
        "created_at",
        sa.DateTime(timezone=True),
        server_default=sa.text("now()"),
        nullable=False,
    )


def _extra() -> sa.Column:
    return sa.Column(
        "extra",
        postgresql.JSONB(astext_type=sa.Text()),
        server_default=sa.text("'{}'::jsonb"),
        nullable=False,
    )


def upgrade() -> None:
    op.create_table(
        "companies",
        _uuid_pk(),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("tax_id", sa.String(length=32), server_default="", nullable=False),
        sa.Column("tax_office", sa.String(), server_default="", nullable=False),
        sa.Column("sector", sa.String(), server_default="general", nullable=False),
        sa.Column("city", sa.String(), server_default="", nullable=False),
        sa.Column("email", sa.String(), server_default="", nullable=False),
        sa.Column("legal_form", sa.String(), server_default="ltd", nullable=False),
        sa.Column("currency", sa.String(length=8), server_default="TRY", nullable=False),
        sa.Column(
            "cash_balance", sa.Numeric(16, 2), server_default="0", nullable=False
        ),
        sa.Column(
            "seeded", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
        sa.Column("seeded_at", sa.String(), nullable=True),
        sa.Column("owner_user_id", sa.String(), nullable=True),
        _extra(),
        _created_at(),
        sa.PrimaryKeyConstraint("id"),
    )

    # Link accounts to their workspace. Existing rows (if any) keep NULL and
    # land on the frontend's company-setup recovery screen.
    op.add_column(
        "users",
        sa.Column("display_name", sa.String(), server_default="", nullable=False),
    )
    op.add_column(
        "users", sa.Column("role", sa.String(), server_default="owner", nullable=False)
    )
    op.add_column(
        "users",
        sa.Column("company_id", postgresql.UUID(as_uuid=False), nullable=True),
    )
    op.create_index("ix_users_company_id", "users", ["company_id"])
    op.create_foreign_key(
        "fk_users_company_id",
        "users",
        "companies",
        ["company_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.create_table(
        "company_invoices",
        _uuid_pk(),
        _company_fk(),
        sa.Column("number", sa.String(), server_default="", nullable=False),
        sa.Column("vendor", sa.String(), server_default="", nullable=False),
        sa.Column("tax_id", sa.String(length=32), server_default="", nullable=False),
        sa.Column("direction", sa.String(), server_default="purchase", nullable=False),
        sa.Column("issue_date", sa.Date(), nullable=True),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("paid_date", sa.Date(), nullable=True),
        sa.Column("net_amount", sa.Numeric(16, 2), server_default="0", nullable=False),
        sa.Column("vat_amount", sa.Numeric(16, 2), server_default="0", nullable=False),
        sa.Column("amount", sa.Numeric(16, 2), server_default="0", nullable=False),
        sa.Column("status", sa.String(), server_default="pending", nullable=False),
        sa.Column("category", sa.String(), server_default="other", nullable=False),
        sa.Column("source", sa.String(), server_default="manual", nullable=False),
        sa.Column("ocr_confidence", sa.Numeric(5, 4), nullable=True),
        sa.Column(
            "needs_review", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "demo", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
        _extra(),
        _created_at(),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_company_invoices_company_id", "company_invoices", ["company_id"]
    )
    op.create_index(
        "ix_company_invoices_issue_date", "company_invoices", ["issue_date"]
    )

    op.create_table(
        "company_transactions",
        _uuid_pk(),
        _company_fk(),
        sa.Column("date", sa.Date(), nullable=True),
        sa.Column("amount", sa.Numeric(16, 2), server_default="0", nullable=False),
        sa.Column("type", sa.String(), server_default="expense", nullable=False),
        sa.Column("category", sa.String(), server_default="other", nullable=False),
        sa.Column("description", sa.String(), server_default="", nullable=False),
        sa.Column("vendor", sa.String(), server_default="", nullable=False),
        sa.Column("invoice_id", sa.String(), nullable=True),
        sa.Column(
            "demo", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
        _extra(),
        _created_at(),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_company_transactions_company_id", "company_transactions", ["company_id"]
    )
    op.create_index("ix_company_transactions_date", "company_transactions", ["date"])

    op.create_table(
        "company_products",
        _uuid_pk(),
        _company_fk(),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("sku", sa.String(), server_default="", nullable=False),
        sa.Column("stock", sa.Integer(), server_default="0", nullable=False),
        sa.Column("min_stock", sa.Integer(), server_default="0", nullable=False),
        sa.Column("unit_price", sa.Numeric(16, 2), server_default="0", nullable=False),
        sa.Column(
            "monthly_usage", sa.Numeric(16, 2), server_default="0", nullable=False
        ),
        sa.Column("unit", sa.String(), server_default="adet", nullable=False),
        sa.Column(
            "demo", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
        _extra(),
        _created_at(),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_company_products_company_id", "company_products", ["company_id"]
    )

    op.create_table(
        "company_employees",
        _uuid_pk(),
        _company_fk(),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("role", sa.String(), server_default="", nullable=False),
        sa.Column(
            "gross_salary", sa.Numeric(16, 2), server_default="0", nullable=False
        ),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("sgk_no", sa.String(length=32), server_default="", nullable=False),
        sa.Column(
            "demo", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
        _extra(),
        _created_at(),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_company_employees_company_id", "company_employees", ["company_id"]
    )

    op.create_table(
        "company_tax_obligations",
        _uuid_pk(),
        _company_fk(),
        sa.Column("type", sa.String(), server_default="kdv", nullable=False),
        sa.Column("name", sa.String(), server_default="", nullable=False),
        sa.Column("period", sa.String(length=16), server_default="", nullable=False),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("amount", sa.Numeric(16, 2), server_default="0", nullable=False),
        sa.Column("status", sa.String(), server_default="draft", nullable=False),
        sa.Column("paid_date", sa.Date(), nullable=True),
        sa.Column(
            "demo", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
        _extra(),
        _created_at(),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_company_tax_obligations_company_id",
        "company_tax_obligations",
        ["company_id"],
    )
    op.create_index(
        "ix_company_tax_obligations_due_date", "company_tax_obligations", ["due_date"]
    )


def downgrade() -> None:
    op.drop_table("company_tax_obligations")
    op.drop_table("company_employees")
    op.drop_table("company_products")
    op.drop_table("company_transactions")
    op.drop_table("company_invoices")
    op.drop_constraint("fk_users_company_id", "users", type_="foreignkey")
    op.drop_index("ix_users_company_id", table_name="users")
    op.drop_column("users", "company_id")
    op.drop_column("users", "role")
    op.drop_column("users", "display_name")
    op.drop_table("companies")
