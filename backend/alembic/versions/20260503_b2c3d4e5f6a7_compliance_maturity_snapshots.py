"""Compliance maturity snapshots fuer den Department-Reife-Trend.

Eine Zeile pro (department, snapshot_date) mit den fuenf Sub-Scores
(VVT/DSFA/AVV/TOM/Velocity) und dem gewichteten Composite-Score.
Befuellt von einem taeglichen Celery-Beat-Job.

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-05-03 12:00:00.000000
"""

from __future__ import annotations

from alembic import op

revision: str = "b2c3d4e5f6a7"
down_revision: str | None = "a1b2c3d4e5f6"
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS compliance_maturity_snapshots (
            id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            department      VARCHAR(200) NOT NULL,
            snapshot_date   DATE NOT NULL,
            vvt_score       DOUBLE PRECISION NOT NULL DEFAULT 0,
            dsfa_score      DOUBLE PRECISION NOT NULL DEFAULT 0,
            avv_score       DOUBLE PRECISION NOT NULL DEFAULT 0,
            tom_score       DOUBLE PRECISION NOT NULL DEFAULT 0,
            velocity_score  DOUBLE PRECISION NOT NULL DEFAULT 0,
            composite_score DOUBLE PRECISION NOT NULL DEFAULT 0,
            created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_maturity_dept_date
            ON compliance_maturity_snapshots (department, snapshot_date)
    """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_maturity_snapshot_date
            ON compliance_maturity_snapshots (snapshot_date)
    """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS compliance_maturity_snapshots")
