"""Apply Alembic migrations up to head.

Invoked on application startup so the database schema always matches the ORM
models without a manual ``alembic upgrade head`` step. Without this, adding a
column/table to a model raises a runtime error on the first query that touches
it (the DB is missing the column), surfacing as an opaque 500 to clients.
"""
from __future__ import annotations

import logging
from pathlib import Path

from alembic import command
from alembic.config import Config

logger = logging.getLogger(__name__)

# .../backend  (this file is .../backend/app/db/migrate.py)
BACKEND_DIR = Path(__file__).resolve().parents[2]


def run_upgrade_to_head() -> None:
    """Upgrade the database to the latest revision (idempotent)."""
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    # Use absolute paths so resolution does not depend on the working directory.
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    command.upgrade(cfg, "head")
    logger.info("Database migrations applied (head).")
