"""Retention Policy Lifecycle Engine: automatisch Vorgänge archivieren, die ihre Aufbewahrungsfrist überschritten haben."""
import logging
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db import ActivityLogModel, CaseModel

logger = logging.getLogger(__name__)


async def scan_cases_for_retention(db: AsyncSession, dry_run: bool = False) -> list[dict]:
    """Archiviert Vorgänge, bei denen retention_months seit dem Abschluss (completed_at)
    bzw. der Erstellung (created_at) abgelaufen ist.

    Aufbewahrungsfrist-Logik (DSGVO Art. 5 Abs. 1 lit. e – Speicherbegrenzung):
      - Basis ist completed_at (Zeitpunkt des Abschlusses), falls gesetzt.
      - Fallback auf created_at wenn completed_at NULL ist.
      - updated_at wird bewusst NICHT verwendet, da automatische Re-Checks und
        Statusänderungen dieses Datum fortlaufend aktualisieren würden.

    Returns list of cases that were (or would be, if dry_run=True) archived.
    """
    stmt = text("""
        SELECT id, title, department, retention_months, created_at, completed_at,
               COALESCE(completed_at, created_at) AS retention_base
        FROM cases
        WHERE archived_at IS NULL
          AND retention_months IS NOT NULL
          AND COALESCE(completed_at, created_at) < NOW() - (retention_months * INTERVAL '1 month')
        ORDER BY COALESCE(completed_at, created_at) ASC
    """)
    result = await db.execute(stmt)
    rows = result.mappings().all()

    archived = []
    for row in rows:
        case_id = row["id"]
        retention_base = row["retention_base"]
        archived.append({
            "case_id": str(case_id),
            "title": row["title"],
            "department": row["department"],
            "retention_months": row["retention_months"],
            "retention_base": retention_base.isoformat() if retention_base else None,
            "completed_at": row["completed_at"].isoformat() if row["completed_at"] else None,
        })

        if not dry_run:
            case_result = await db.execute(select(CaseModel).where(CaseModel.id == case_id))
            case = case_result.scalar_one_or_none()
            if case:
                case.archived_at = datetime.now(timezone.utc)
                activity = ActivityLogModel(
                    case_id=case_id,
                    event_type="retention_auto_archived",
                    payload={
                        "retention_months": case.retention_months,
                        "archived_by": "system",
                    },
                )
                db.add(activity)
                logger.info(
                    "Auto-archiving case",
                    extra={"case_id": str(case_id), "retention_months": case.retention_months},
                )

    if not dry_run and archived:
        await db.flush()

    logger.info(
        "Retention scan complete",
        extra={"archived": len(archived), "dry_run": dry_run},
    )
    return archived
