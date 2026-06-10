"""Datenschutzerklaerungen werden vorgangsspezifisch.

Eine Datenschutzerklaerung gehoert ab jetzt zu genau einem Case.
- Bestehende organisationsweite Erklaerungen werden geloescht (per User-Vorgabe).
- Neue Spalten: case_id (FK auf cases, ON DELETE CASCADE), version (int).
- Spalten org_name und department entfallen (kommen jetzt aus dem Case).

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-05-07 00:00:00.000000
"""

from __future__ import annotations

from alembic import op

revision: str = "c3d4e5f6a7b8"
down_revision: str | None = "b2c3d4e5f6a7"
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


def upgrade() -> None:
    # Idempotent gegen Fresh-Installs: privacy_policies kann via create_all
    # bereits mit neuem Schema existieren. Deshalb IF EXISTS / IF NOT EXISTS
    # ueberall, plus DO-Block fuer DELETE.

    # 1. Bestand loeschen (User-Vorgabe). Nur falls Tabelle existiert.
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT FROM information_schema.tables WHERE table_name='privacy_policies') THEN
                DELETE FROM privacy_policies;
            END IF;
        END $$
    """
    )

    # 2. case_id als FK auf cases ergaenzen (ON DELETE CASCADE).
    #    NOT NULL ist sicher, da Tabelle in Schritt 1 geleert wurde.
    op.execute(
        """
        ALTER TABLE IF EXISTS privacy_policies
        ADD COLUMN IF NOT EXISTS case_id UUID
    """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT FROM information_schema.columns
                       WHERE table_name='privacy_policies' AND column_name='case_id'
                         AND is_nullable='YES') THEN
                ALTER TABLE privacy_policies ALTER COLUMN case_id SET NOT NULL;
            END IF;
        END $$
    """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.table_constraints
                WHERE table_name='privacy_policies'
                  AND constraint_name='privacy_policies_case_id_fkey'
            ) AND EXISTS (
                SELECT 1 FROM information_schema.tables WHERE table_name='privacy_policies'
            ) THEN
                ALTER TABLE privacy_policies
                ADD CONSTRAINT privacy_policies_case_id_fkey
                FOREIGN KEY (case_id) REFERENCES cases(id) ON DELETE CASCADE;
            END IF;
        END $$
    """
    )

    # 3. Version (pro Case hochzaehlend) ergaenzen.
    op.execute(
        """
        ALTER TABLE IF EXISTS privacy_policies
        ADD COLUMN IF NOT EXISTS version INTEGER NOT NULL DEFAULT 1
    """
    )

    # 4. Index fuer Case-Lookup.
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_privacy_policies_case_id
        ON privacy_policies (case_id)
    """
    )

    # 5. Redundante Spalten entfernen (kommen jetzt aus dem Case).
    op.execute("ALTER TABLE IF EXISTS privacy_policies DROP COLUMN IF EXISTS org_name")
    op.execute(
        "ALTER TABLE IF EXISTS privacy_policies DROP COLUMN IF EXISTS department"
    )


def downgrade() -> None:
    # Achtung: Daten gehen beim Downgrade verloren (Case-Bezug ist nicht rekonstruierbar).
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT FROM information_schema.tables WHERE table_name='privacy_policies') THEN
                DELETE FROM privacy_policies;
            END IF;
        END $$
    """
    )
    op.execute("DROP INDEX IF EXISTS ix_privacy_policies_case_id")
    op.execute(
        "ALTER TABLE IF EXISTS privacy_policies DROP CONSTRAINT IF EXISTS privacy_policies_case_id_fkey"
    )
    op.execute("ALTER TABLE IF EXISTS privacy_policies DROP COLUMN IF EXISTS version")
    op.execute("ALTER TABLE IF EXISTS privacy_policies DROP COLUMN IF EXISTS case_id")
    op.execute(
        "ALTER TABLE IF EXISTS privacy_policies ADD COLUMN IF NOT EXISTS org_name VARCHAR(300)"
    )
    op.execute(
        "ALTER TABLE IF EXISTS privacy_policies ADD COLUMN IF NOT EXISTS department VARCHAR(200)"
    )
