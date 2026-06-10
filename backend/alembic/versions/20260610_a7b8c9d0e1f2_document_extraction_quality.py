"""Extraction quality signals on documents

Adds nullable quality columns populated on successful extraction:
- documents.extraction_char_count INTEGER          — length of extracted text
- documents.extraction_page_count INTEGER          — number of pages (PDF; NULL otherwise)
- documents.extraction_ocr_ratio DOUBLE PRECISION  — fraction of pages extracted via OCR

These let weak extractions (e.g. scans with little recovered text) be flagged for review and
factored into downstream confidence.

Revision ID: a7b8c9d0e1f2
Revises: f6a7b8c9d0e1
Create Date: 2026-06-10 00:00:00.000000
"""

from __future__ import annotations

from alembic import op

revision: str = "a7b8c9d0e1f2"
down_revision: str | None = "f6a7b8c9d0e1"
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE IF EXISTS documents ADD COLUMN IF NOT EXISTS extraction_char_count INTEGER"
    )
    op.execute(
        "ALTER TABLE IF EXISTS documents ADD COLUMN IF NOT EXISTS extraction_page_count INTEGER"
    )
    op.execute(
        "ALTER TABLE IF EXISTS documents ADD COLUMN IF NOT EXISTS extraction_ocr_ratio DOUBLE PRECISION"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE IF EXISTS documents DROP COLUMN IF EXISTS extraction_ocr_ratio"
    )
    op.execute(
        "ALTER TABLE IF EXISTS documents DROP COLUMN IF EXISTS extraction_page_count"
    )
    op.execute(
        "ALTER TABLE IF EXISTS documents DROP COLUMN IF EXISTS extraction_char_count"
    )
