"""Baseline migration – captures additive schema changes applied to date.

All statements use IF NOT EXISTS / CREATE INDEX CONCURRENTLY IF NOT EXISTS,
so this migration is safe to run on:
  - Fresh installs (create_all already created all tables; these are no-ops)
  - Existing deployments (adds only the missing columns/indexes)

Any schema changes going forward must be created via:
    alembic revision --autogenerate -m "description"

Revision ID: a1b2c3d4e5f6
Revises:
Create Date: 2025-04-15 20:00:00.000000
"""

from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: str | None = None
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


def upgrade() -> None:
    # ---- Documents ----
    op.execute(
        "ALTER TABLE documents ADD COLUMN IF NOT EXISTS extraction_method VARCHAR(20)"
    )
    op.execute(
        "ALTER TABLE documents ADD COLUMN IF NOT EXISTS extraction_status VARCHAR(20)"
    )
    op.execute("ALTER TABLE documents ADD COLUMN IF NOT EXISTS extraction_error TEXT")

    # ---- Findings ----
    op.execute(
        "ALTER TABLE findings ADD COLUMN IF NOT EXISTS source_strategy VARCHAR(20)"
    )
    op.execute("ALTER TABLE findings ADD COLUMN IF NOT EXISTS due_date TIMESTAMPTZ")
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_findings_created_at ON findings (created_at)"
    )

    # ---- Users ----
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS oidc_sub VARCHAR(500) NULL")
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS ix_users_oidc_sub ON users (oidc_sub) WHERE oidc_sub IS NOT NULL"
    )
    op.execute(
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS role VARCHAR(20) NOT NULL DEFAULT 'viewer'"
    )
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS display_name VARCHAR(200)")
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS preferences JSONB")

    # ---- Cases ----
    op.execute(
        "ALTER TABLE cases ADD COLUMN IF NOT EXISTS processing_context VARCHAR(80) NULL"
    )
    op.execute(
        "ALTER TABLE cases ADD COLUMN IF NOT EXISTS special_category_data BOOLEAN NOT NULL DEFAULT false"
    )
    op.execute(
        "ALTER TABLE cases ADD COLUMN IF NOT EXISTS international_transfer BOOLEAN NOT NULL DEFAULT false"
    )
    op.execute(
        "ALTER TABLE cases ADD COLUMN IF NOT EXISTS recheck_interval_days INTEGER"
    )
    op.execute(
        "ALTER TABLE cases ADD COLUMN IF NOT EXISTS last_rechecked_at TIMESTAMPTZ"
    )
    op.execute(
        "ALTER TABLE cases ADD COLUMN IF NOT EXISTS last_notified_at TIMESTAMPTZ"
    )
    op.execute("ALTER TABLE cases ADD COLUMN IF NOT EXISTS completed_at TIMESTAMPTZ")
    op.execute(
        "ALTER TABLE cases ADD COLUMN IF NOT EXISTS auto_run_checks BOOLEAN NOT NULL DEFAULT false"
    )

    # ---- DSR requests ----
    op.execute("ALTER TABLE dsr_requests ADD COLUMN IF NOT EXISTS draft_response TEXT")
    op.execute(
        "ALTER TABLE dsr_requests ADD COLUMN IF NOT EXISTS last_notified_at TIMESTAMPTZ"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_dsr_requests_status ON dsr_requests (status)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_dsr_requests_response_deadline ON dsr_requests (response_deadline)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_dsr_activity_log_request_id ON dsr_activity_log (request_id)"
    )

    # ---- Data breaches ----
    op.execute(
        "ALTER TABLE data_breaches ADD COLUMN IF NOT EXISTS authority_reference VARCHAR(200)"
    )
    op.execute(
        "ALTER TABLE data_breaches ADD COLUMN IF NOT EXISTS draft_notification TEXT"
    )
    op.execute(
        "ALTER TABLE data_breaches ADD COLUMN IF NOT EXISTS last_notified_at TIMESTAMPTZ"
    )

    # ---- AVV contracts ----
    op.execute("ALTER TABLE avv_contracts ADD COLUMN IF NOT EXISTS check_result JSONB")
    op.execute("ALTER TABLE avv_contracts ADD COLUMN IF NOT EXISTS risk_score INTEGER")
    op.execute(
        "ALTER TABLE avv_contracts ADD COLUMN IF NOT EXISTS risk_level VARCHAR(20)"
    )
    op.execute(
        "ALTER TABLE avv_contracts ADD COLUMN IF NOT EXISTS risk_assessment JSONB"
    )
    op.execute(
        "ALTER TABLE avv_contracts ADD COLUMN IF NOT EXISTS risk_assessed_at TIMESTAMPTZ"
    )
    op.execute(
        "ALTER TABLE avv_contracts ADD COLUMN IF NOT EXISTS last_notified_at TIMESTAMPTZ"
    )

    # ---- TOM measures ----
    op.execute("ALTER TABLE tom_measures ADD COLUMN IF NOT EXISTS evidence TEXT")

    # ---- Case templates ----
    op.execute(
        "ALTER TABLE case_templates ADD COLUMN IF NOT EXISTS is_builtin BOOLEAN NOT NULL DEFAULT false"
    )

    # ---- Indexes on high-traffic FKs ----
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_finding_chat_messages_finding_id ON finding_chat_messages (finding_id)"
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_dsfa_jobs_case_id ON dsfa_jobs (case_id)")


def downgrade() -> None:
    # Baseline migration is intentionally irreversible.
    # Dropping columns from a production database requires a separate,
    # carefully reviewed migration with explicit data-loss acknowledgment.
    pass
