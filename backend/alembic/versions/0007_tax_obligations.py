"""tax obligations

Revision ID: 0007_tax_obligations
Revises: 0006_bank_transactions
Create Date: 2026-06-18 00:00:05

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0007_tax_obligations"
down_revision: Union[str, None] = "0006_bank_transactions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "tax_obligations",
        sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("type", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("period", sa.String(), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("estimated_amount", sa.Numeric(14, 2), nullable=True),
        sa.Column("paid_amount", sa.Numeric(14, 2), nullable=True),
        sa.Column("status", sa.String(), nullable=False, server_default="pending"),
        sa.Column("paid_date", sa.Date(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "type", "period", name="uq_tax_obligation_period"),
    )
    op.create_index(
        "ix_tax_obligations_user_id", "tax_obligations", ["user_id"]
    )
    op.create_index("ix_tax_obligations_due_date", "tax_obligations", ["due_date"])


def downgrade() -> None:
    op.drop_index("ix_tax_obligations_due_date", table_name="tax_obligations")
    op.drop_index("ix_tax_obligations_user_id", table_name="tax_obligations")
    op.drop_table("tax_obligations")
