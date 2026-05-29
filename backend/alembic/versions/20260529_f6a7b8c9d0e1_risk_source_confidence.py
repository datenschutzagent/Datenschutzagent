"""Provenance columns on avv_contracts for confidence-policy outcomes

Adds:
- avv_contracts.risk_source VARCHAR(20)  — 'llm' | 'rules' | 'hybrid'
- avv_contracts.risk_confidence DOUBLE PRECISION — self-reported LLM confidence

DSFA confidence + source already live in DSFAAssessmentModel.payload (JSONB),
no schema change needed there. The DSFA fallback also emits an ActivityLog
row of event_type 'risk.fallback_triggered' (no schema change either —
activity_log accepts any event_type string).

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-05-29 00:30:00.000000
"""
from __future__ import annotations

from alembic import op


revision: str = "f6a7b8c9d0e1"
down_revision: str | None = "e5f6a7b8c9d0"
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE IF EXISTS avv_contracts
        ADD COLUMN IF NOT EXISTS risk_source VARCHAR(20)
    """)
    op.execute("""
        ALTER TABLE IF EXISTS avv_contracts
        ADD COLUMN IF NOT EXISTS risk_confidence DOUBLE PRECISION
    """)


def downgrade() -> None:
    op.execute("ALTER TABLE IF EXISTS avv_contracts DROP COLUMN IF EXISTS risk_confidence")
    op.execute("ALTER TABLE IF EXISTS avv_contracts DROP COLUMN IF EXISTS risk_source")
