"""User notifications_enabled flag + Critical findings notification tracking

Adds:
- users.notifications_enabled BOOLEAN NOT NULL DEFAULT true
- findings.last_notified_at TIMESTAMP — Cooldown-Marker für CRITICAL-Findings-
  Benachrichtigungen (analog zu cases.last_notified_at).

Migrationen sind idempotent (IF NOT EXISTS), damit Fresh-Installs über
create_all() nicht in Konflikt geraten.

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-05-19 00:00:00.000000
"""

from __future__ import annotations

from alembic import op

revision: str = "d4e5f6a7b8c9"
down_revision: str | None = "c3d4e5f6a7b8"
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


def upgrade() -> None:
    # User-Master-Switch für Benachrichtigungen.
    op.execute(
        """
        ALTER TABLE IF EXISTS users
        ADD COLUMN IF NOT EXISTS notifications_enabled BOOLEAN NOT NULL DEFAULT true
    """
    )

    # Cooldown-Marker für CRITICAL-Findings-Benachrichtigungen.
    op.execute(
        """
        ALTER TABLE IF EXISTS findings
        ADD COLUMN IF NOT EXISTS last_notified_at TIMESTAMPTZ
    """
    )


def downgrade() -> None:
    op.execute("ALTER TABLE IF EXISTS findings DROP COLUMN IF EXISTS last_notified_at")
    op.execute(
        "ALTER TABLE IF EXISTS users DROP COLUMN IF EXISTS notifications_enabled"
    )
