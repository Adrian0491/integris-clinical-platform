"""
Alembic env.py — configured for autogenerate against all CDTool models.

Run from backend/ directory:
    PYTHONPATH=..:. alembic upgrade head
    PYTHONPATH=..:. alembic revision --autogenerate -m "describe change"
"""
from __future__ import annotations

import os
import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

# ---------------------------------------------------------------------------
# Ensure the project root and backend/ are on the Python path so that
# `from app.models import Base` resolves correctly.
# ---------------------------------------------------------------------------
_here = Path(__file__).resolve().parent        # backend/alembic/
_backend = _here.parent                        # backend/
_project_root = _backend.parent               # CDTool/

for path in (_project_root, _backend):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

# Import all models so Alembic's autogenerate can see every table.
from app.models import Base  # noqa: E402  (must be after sys.path manipulation)

# ---------------------------------------------------------------------------
# Alembic Config object
# ---------------------------------------------------------------------------
config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# Derive the DB URL from the environment (overrides alembic.ini sqlalchemy.url).
DATABASE_URL = os.environ.get("DATABASE_URL", "")
if DATABASE_URL:
    config.set_main_option("sqlalchemy.url", DATABASE_URL)


# ---------------------------------------------------------------------------
# Migration runners
# ---------------------------------------------------------------------------

def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
