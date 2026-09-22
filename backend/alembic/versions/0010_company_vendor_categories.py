"""company vendor categories — what the classifier has learned

The keyword rules in ``expense_classifier.py`` are a first guess. A user who
files a vendor under a different category is teaching the app something only
that company knows, so the correction is stored with the company's data and
posted back to the stateless ``/api/compute/classify`` on the next lookup.

Superseding ``vendor_categories`` from 0008, which is user-scoped and backs the
deprecated ``/api/expenses`` routes. That table is left in place; nothing calls
it.

Revision ID: 0010_company_vendor_categories
Revises: 0009_company_workspace
Create Date: 2026-09-13 00:00:00

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0010_company_vendor_categories"
down_revision: Union[str, None] = "0009_company_workspace"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "company_vendor_categories",
        sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("vendor_key", sa.String(), nullable=False),
        sa.Column("vendor", sa.String(), server_default="", nullable=False),
        sa.Column("category", sa.String(), server_default="other", nullable=False),
        sa.Column(
            "corrected", sa.Boolean(), server_default=sa.text("true"), nullable=False
        ),
        sa.Column(
            "extra",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_company_vendor_categories_company_id",
        "company_vendor_categories",
        ["company_id"],
    )
    # Not unique: the workspace router is generic CRUD with no upsert, and a
    # conflict would fail an invoice save. The client patches the row it found
    # and reads resolve a duplicate by taking the newest.
    op.create_index(
        "ix_company_vendor_categories_vendor_key",
        "company_vendor_categories",
        ["vendor_key"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_company_vendor_categories_vendor_key",
        table_name="company_vendor_categories",
    )
    op.drop_index(
        "ix_company_vendor_categories_company_id",
        table_name="company_vendor_categories",
    )
    op.drop_table("company_vendor_categories")
