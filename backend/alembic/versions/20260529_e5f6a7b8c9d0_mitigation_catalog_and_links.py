"""Mitigation catalog: link tables + AVV inherent/residual columns

Adds:
- avv_contracts.inherent_risk_score, inherent_risk_level (nullable)
- case_mitigation_links: case ↔ catalog mitigation (DSFA-side)
- avv_mitigation_links: AVV contract ↔ catalog mitigation

Migrations are idempotent so fresh installs via Base.metadata.create_all()
do not collide.

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-05-29 00:00:00.000000
"""
from __future__ import annotations

from alembic import op


revision: str = "e5f6a7b8c9d0"
down_revision: str | None = "d4e5f6a7b8c9"
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


def upgrade() -> None:
    # AVV inherent risk columns (residual = existing risk_score/risk_level).
    op.execute("""
        ALTER TABLE IF EXISTS avv_contracts
        ADD COLUMN IF NOT EXISTS inherent_risk_score INTEGER
    """)
    op.execute("""
        ALTER TABLE IF EXISTS avv_contracts
        ADD COLUMN IF NOT EXISTS inherent_risk_level VARCHAR(20)
    """)

    # Case ↔ mitigation (DSFA).
    op.execute("""
        CREATE TABLE IF NOT EXISTS case_mitigation_links (
            id UUID PRIMARY KEY,
            case_id UUID NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
            mitigation_id VARCHAR(80) NOT NULL,
            tom_id UUID REFERENCES tom_measures(id) ON DELETE SET NULL,
            evidence_doc_id UUID REFERENCES documents(id) ON DELETE SET NULL,
            applied_by VARCHAR(200) NOT NULL DEFAULT '',
            notes TEXT,
            applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT uq_case_mitigation_links_case_mitigation UNIQUE (case_id, mitigation_id)
        )
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_case_mitigation_links_case_id
        ON case_mitigation_links (case_id)
    """)

    # AVV contract ↔ mitigation.
    op.execute("""
        CREATE TABLE IF NOT EXISTS avv_mitigation_links (
            id UUID PRIMARY KEY,
            avv_contract_id UUID NOT NULL REFERENCES avv_contracts(id) ON DELETE CASCADE,
            mitigation_id VARCHAR(80) NOT NULL,
            tom_id UUID REFERENCES tom_measures(id) ON DELETE SET NULL,
            applied_by VARCHAR(200) NOT NULL DEFAULT '',
            notes TEXT,
            applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT uq_avv_mitigation_links_contract_mitigation UNIQUE (avv_contract_id, mitigation_id)
        )
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_avv_mitigation_links_contract_id
        ON avv_mitigation_links (avv_contract_id)
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS avv_mitigation_links")
    op.execute("DROP TABLE IF EXISTS case_mitigation_links")
    op.execute("ALTER TABLE IF EXISTS avv_contracts DROP COLUMN IF EXISTS inherent_risk_level")
    op.execute("ALTER TABLE IF EXISTS avv_contracts DROP COLUMN IF EXISTS inherent_risk_score")
