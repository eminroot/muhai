"""inventory movements

Revision ID: 0005_inventory_movements
Revises: 0004_compliance_alerts
Create Date: 2026-06-18 00:00:03

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005_inventory_movements"
down_revision: Union[str, None] = "0004_compliance_alerts"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    movement_type = postgresql.ENUM(
        "purchase", "sale", "adjustment", name="movement_type", create_type=False
    )
    movement_type.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "inventory_movements",
        sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("product_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("type", movement_type, nullable=False),
        sa.Column("quantity", sa.Numeric(14, 3), nullable=False),
        sa.Column("invoice_id", sa.String(), nullable=True),
        sa.Column(
            "date",
            sa.Date(),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("notes", sa.String(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_inventory_movements_user_id", "inventory_movements", ["user_id"]
    )
    op.create_index(
        "ix_inventory_movements_product_id", "inventory_movements", ["product_id"]
    )
    op.create_index(
        "ix_inventory_movements_date", "inventory_movements", ["date"]
    )


def downgrade() -> None:
    op.drop_index("ix_inventory_movements_date", table_name="inventory_movements")
    op.drop_index(
        "ix_inventory_movements_product_id", table_name="inventory_movements"
    )
    op.drop_index(
        "ix_inventory_movements_user_id", table_name="inventory_movements"
    )
    op.drop_table("inventory_movements")
    sa.Enum(name="movement_type").drop(op.get_bind(), checkfirst=True)
