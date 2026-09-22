"""employee payroll fields (tckn, start_date, status)

Revision ID: 0003_employee_payroll_fields
Revises: 0002_muhai_scores
Create Date: 2026-06-18 00:00:01

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003_employee_payroll_fields"
down_revision: Union[str, None] = "0002_muhai_scores"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("employees", sa.Column("tckn", sa.String(), nullable=True))
    op.add_column("employees", sa.Column("start_date", sa.Date(), nullable=True))
    op.add_column(
        "employees",
        sa.Column(
            "status", sa.String(), nullable=False, server_default="active"
        ),
    )


def downgrade() -> None:
    op.drop_column("employees", "status")
    op.drop_column("employees", "start_date")
    op.drop_column("employees", "tckn")
