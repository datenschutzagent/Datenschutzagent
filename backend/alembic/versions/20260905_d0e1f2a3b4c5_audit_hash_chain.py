"""Audit log: hash chain, insert sequence and resource id

Phase 1 S6 of the Qualitätsplan. Adds to api_audit_log:
- seq          BIGINT identity   monotonic insert order for the chain
- resource_id  VARCHAR(36)       concrete object for audited reads (document id, …)
- prev_hash    VARCHAR(64)       entry_hash of the previous row (seq order)
- entry_hash   VARCHAR(64)       sha256 over prev_hash + the row's fields

Existing rows keep NULL hashes; chain verification starts at the first hashed row.

Revision ID: d0e1f2a3b4c5
Revises: c9d0e1f2a3b4
Create Date: 2026-09-05 00:00:00.000000
"""

from __future__ import annotations

from alembic import op

revision: str = "d0e1f2a3b4c5"
down_revision: str | None = "c9d0e1f2a3b4"
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE api_audit_log ADD COLUMN IF NOT EXISTS seq BIGINT "
        "GENERATED ALWAYS AS IDENTITY"
    )
    op.execute(
        "ALTER TABLE api_audit_log ADD COLUMN IF NOT EXISTS resource_id VARCHAR(36)"
    )
    op.execute(
        "ALTER TABLE api_audit_log ADD COLUMN IF NOT EXISTS prev_hash VARCHAR(64)"
    )
    op.execute(
        "ALTER TABLE api_audit_log ADD COLUMN IF NOT EXISTS entry_hash VARCHAR(64)"
    )
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS ix_api_audit_log_seq ON api_audit_log (seq)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_api_audit_log_seq")
    op.execute("ALTER TABLE api_audit_log DROP COLUMN IF EXISTS entry_hash")
    op.execute("ALTER TABLE api_audit_log DROP COLUMN IF EXISTS prev_hash")
    op.execute("ALTER TABLE api_audit_log DROP COLUMN IF EXISTS resource_id")
    op.execute("ALTER TABLE api_audit_log DROP COLUMN IF EXISTS seq")
