"""drop the user-scoped tables the workspace replaced

Revisions 0001-0008 built a per-user schema -- invoices, transactions,
employees, products, muhai_scores, compliance_alerts, inventory_movements,
bank_transactions, tax_obligations, vendor_categories -- behind the
``/api/invoices``-style routes. 0009 replaced all of it with the company
workspace and nothing has called those routes since; 0010 moved the last live
idea in them (vendor-category learning) onto ``company_vendor_categories``.

The routes, models and schemas were deleted on 2026-09-13. This drops the
tables behind them. Recover the code from commit 5cb59c0 if any of it is ever
wanted back -- ``bank_service.py`` in particular, which parsed Turkish bank
statement CSVs and fuzzy-matched rows to invoices.

Revision ID: 0011_drop_legacy_tables
Revises: 0010_company_vendor_categories
Create Date: 2026-09-13 00:00:00

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# Kept short on purpose: alembic_version.version_num is varchar(32) and a
# longer id fails at the very end of the upgrade, after the DDL has run.
revision: str = "0011_drop_legacy_tables"
down_revision: Union[str, None] = "0010_company_vendor_categories"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Children before parents: inventory_movements references products and
# invoices, bank_transactions references invoices.
_TABLES = (
    "inventory_movements",
    "bank_transactions",
    "compliance_alerts",
    "muhai_scores",
    "tax_obligations",
    "vendor_categories",
    "invoices",
    "transactions",
    "employees",
    "products",
)


def upgrade() -> None:
    # IF EXISTS because a database created after these tables were deleted
    # (a fresh clone running 0001 onwards) still replays every revision.
    for table in _TABLES:
        op.execute(sa.text('DROP TABLE IF EXISTS "%s" CASCADE' % table))


def downgrade() -> None:
    """Deliberately empty.

    Recreating ten empty tables would restore nothing that mattered, and the
    models that described them no longer exist in the codebase. Restore from a
    dump if you ever need the data.
    """
