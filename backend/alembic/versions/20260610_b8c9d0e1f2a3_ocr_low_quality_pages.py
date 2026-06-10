"""OCR low-quality page count on documents

Adds a nullable quality column populated on successful extraction:
- documents.extraction_ocr_low_quality_pages INTEGER — number of pages OCR'd but with almost no
  recovered text (likely lost despite OCR)

Lets reviewers spot scans that did not extract cleanly and factor it into downstream confidence.

Revision ID: b8c9d0e1f2a3
Revises: a7b8c9d0e1f2
Create Date: 2026-06-10 00:00:00.000000
"""
from __future__ import annotations

from alembic import op


revision: str = "b8c9d0e1f2a3"
down_revision: str | None = "a7b8c9d0e1f2"
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


def upgrade() -> None:
    op.execute("ALTER TABLE IF EXISTS documents ADD COLUMN IF NOT EXISTS extraction_ocr_low_quality_pages INTEGER")


def downgrade() -> None:
    op.execute("ALTER TABLE IF EXISTS documents DROP COLUMN IF EXISTS extraction_ocr_low_quality_pages")
