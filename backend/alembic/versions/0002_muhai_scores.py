"""muhai score history

Revision ID: 0002_muhai_scores
Revises: 0001_initial
Create Date: 2026-06-18 00:00:00

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002_muhai_scores"
down_revision: Union[str, None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "muhai_scores",
        sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("total_score", sa.Integer(), nullable=False),
        sa.Column("tax_compliance", sa.Numeric(5, 4), nullable=True),
        sa.Column("sgk_compliance", sa.Numeric(5, 4), nullable=True),
        sa.Column("cash_flow", sa.Numeric(5, 4), nullable=True),
        sa.Column("debt", sa.Numeric(5, 4), nullable=True),
        sa.Column("invoice_collection", sa.Numeric(5, 4), nullable=True),
        sa.Column("inventory", sa.Numeric(5, 4), nullable=True),
        sa.Column("payroll_sustainability", sa.Numeric(5, 4), nullable=True),
        sa.Column("profitability", sa.Numeric(5, 4), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "date", name="uq_muhai_scores_user_date"),
    )
    op.create_index("ix_muhai_scores_user_id", "muhai_scores", ["user_id"])
    op.create_index("ix_muhai_scores_date", "muhai_scores", ["date"])


def downgrade() -> None:
    op.drop_index("ix_muhai_scores_date", table_name="muhai_scores")
    op.drop_index("ix_muhai_scores_user_id", table_name="muhai_scores")
    op.drop_table("muhai_scores")
