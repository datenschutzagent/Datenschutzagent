"""Documents: unique (case_id, type, version)

Phase 2 R6 of the Qualitätsplan. The upload path computes ``max(version) + 1`` as a
read-modify-write; parallel uploads could produce duplicate version numbers. Existing
duplicates (if any) are renumbered per (case_id, type) by upload order before the
constraint is added, so the migration never fails on legacy data.

Revision ID: e1f2a3b4c5d6
Revises: d0e1f2a3b4c5
Create Date: 2026-09-05 00:00:00.000000
"""

from __future__ import annotations

from alembic import op

revision: str = "e1f2a3b4c5d6"
down_revision: str | None = "d0e1f2a3b4c5"
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


def upgrade() -> None:
    # Renumber only the (case_id, type) groups that actually contain duplicates.
    op.execute(
        """
        WITH dup_groups AS (
            SELECT case_id, type
            FROM documents
            GROUP BY case_id, type
            HAVING COUNT(*) <> COUNT(DISTINCT version)
        ),
        ranked AS (
            SELECT d.id,
                   ROW_NUMBER() OVER (
                       PARTITION BY d.case_id, d.type
                       ORDER BY d.version, d.uploaded_at, d.id
                   ) AS rn
            FROM documents d
            JOIN dup_groups g ON g.case_id = d.case_id AND g.type = d.type
        )
        UPDATE documents d
        SET version = r.rn
        FROM ranked r
        WHERE d.id = r.id AND d.version <> r.rn
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint WHERE conname = 'uq_documents_case_type_version'
            ) THEN
                ALTER TABLE documents
                    ADD CONSTRAINT uq_documents_case_type_version
                    UNIQUE (case_id, type, version);
            END IF;
        END $$;
        """
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE documents DROP CONSTRAINT IF EXISTS uq_documents_case_type_version"
    )
