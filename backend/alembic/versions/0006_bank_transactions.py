"""bank transactions

Revision ID: 0006_bank_transactions
Revises: 0005_inventory_movements
Create Date: 2026-06-18 00:00:04

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006_bank_transactions"
down_revision: Union[str, None] = "0005_inventory_movements"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "bank_transactions",
        sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("date", sa.Date(), nullable=True),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("category", sa.String(), nullable=True),
        sa.Column("matched_invoice_id", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=False, server_default="unmatched"),
        sa.Column("bank_account", sa.String(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_bank_transactions_user_id", "bank_transactions", ["user_id"]
    )
    op.create_index("ix_bank_transactions_date", "bank_transactions", ["date"])


def downgrade() -> None:
    op.drop_index("ix_bank_transactions_date", table_name="bank_transactions")
    op.drop_index("ix_bank_transactions_user_id", table_name="bank_transactions")
    op.drop_table("bank_transactions")
