"""Global API audit log table

Introduces api_audit_log to record every mutating API call (POST/PUT/PATCH/DELETE):
- id            UUID        primary key
- user_id       UUID        nullable – no FK so the record outlives the user
- endpoint      VARCHAR(255) path with UUIDs collapsed to {id}
- method        VARCHAR(10)  HTTP method
- status_code   INTEGER      HTTP response status
- request_id    VARCHAR(36)  x-request-id header value
- timestamp     TIMESTAMPTZ  UTC time of the call

Indexes:
- ix_api_audit_log_user_id_timestamp (user_id, timestamp) – per-user timeline queries
- ix_api_audit_log_request_id (request_id) – look up a call by request ID

Revision ID: c9d0e1f2a3b4
Revises: b8c9d0e1f2a3
Create Date: 2026-06-14 00:00:00.000000
"""

from __future__ import annotations

from alembic import op

revision: str = "c9d0e1f2a3b4"
down_revision: str | None = "b8c9d0e1f2a3"
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS api_audit_log (
            id          UUID        NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
            user_id     UUID,
            endpoint    VARCHAR(255) NOT NULL,
            method      VARCHAR(10)  NOT NULL,
            status_code INTEGER      NOT NULL,
            request_id  VARCHAR(36)  NOT NULL DEFAULT '-',
            timestamp   TIMESTAMPTZ  NOT NULL DEFAULT NOW()
        )
        """)
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_api_audit_log_user_id_timestamp "
        "ON api_audit_log (user_id, timestamp)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_api_audit_log_request_id "
        "ON api_audit_log (request_id)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS api_audit_log")
