"""Alembic environment – uses a synchronous psycopg2 connection so that
Alembic's standard migration machinery works without async wrappers.
The runtime (FastAPI) continues to use asyncpg via SQLAlchemy's async engine.
"""
from __future__ import annotations

import os
from logging.config import fileConfig

from sqlalchemy import create_engine, pool

from alembic import context

# Import all models so that Base.metadata is fully populated
from app.models.db import Base  # noqa: F401

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _get_sync_url() -> str:
    """Return a psycopg2 (sync) URL derived from the DATABASE_URL env var.

    The FastAPI runtime uses ``postgresql+asyncpg://...``; Alembic does not
    support async drivers, so we swap the driver component.
    """
    url = os.environ.get("DATABASE_URL", "")
    if not url:
        raise RuntimeError("DATABASE_URL environment variable is not set.")
    # asyncpg → psycopg2 (sync)
    url = url.replace("postgresql+asyncpg://", "postgresql+psycopg2://")
    # bare asyncpg:// edge-case
    url = url.replace("asyncpg://", "postgresql+psycopg2://")
    return url


def run_migrations_offline() -> None:
    """Emit migration SQL to stdout without a live DB connection (--sql flag)."""
    url = _get_sync_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Apply migrations against a live database connection."""
    connectable = create_engine(
        _get_sync_url(),
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
