"""vendor categories

Revision ID: 0008_vendor_categories
Revises: 0007_tax_obligations
Create Date: 2026-06-18 00:00:06

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0008_vendor_categories"
down_revision: Union[str, None] = "0007_tax_obligations"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "vendor_categories",
        sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("vendor_key", sa.String(), nullable=False),
        sa.Column("category", sa.String(), nullable=False),
        sa.Column("corrected", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "vendor_key", name="uq_vendor_category"),
    )
    op.create_index(
        "ix_vendor_categories_user_id", "vendor_categories", ["user_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_vendor_categories_user_id", table_name="vendor_categories")
    op.drop_table("vendor_categories")
