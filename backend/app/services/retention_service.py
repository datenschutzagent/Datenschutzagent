"""Retention Policy Lifecycle Engine: automatisch Vorgänge archivieren, die ihre Aufbewahrungsfrist überschritten haben."""

import logging
from datetime import UTC, datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.db import ActivityLogModel, CaseModel

logger = logging.getLogger(__name__)


def _retention_base_sql() -> str:
    """Return the SQL expression used as retention base date.

    When retention_require_completed=True (default), only cases with a non-NULL
    completed_at are eligible – the retention clock starts when the case is closed.
    When False, we fall back to created_at for legacy/unfinished cases.
    """
    if settings.retention_require_completed:
        return "completed_at"
    return "COALESCE(completed_at, created_at)"


async def scan_cases_for_retention(
    db: AsyncSession, dry_run: bool = False
) -> list[dict]:
    """Archiviert Vorgänge, bei denen retention_months seit dem Abschluss (completed_at)
    bzw. der Erstellung (created_at) abgelaufen ist.

    Aufbewahrungsfrist-Logik (DSGVO Art. 5 Abs. 1 lit. e – Speicherbegrenzung):
      - Basis ist completed_at (Zeitpunkt des Abschlusses).
      - Bei retention_require_completed=False zusätzlich Fallback auf created_at.
      - updated_at wird bewusst NICHT verwendet, da automatische Re-Checks und
        Statusänderungen dieses Datum fortlaufend aktualisieren würden.

    Returns list of cases that were (or would be, if dry_run=True) archived.
    """
    base = _retention_base_sql()
    stmt = text(
        f"""
        SELECT id, title, department, retention_months, created_at, completed_at,
               {base} AS retention_base
        FROM cases
        WHERE archived_at IS NULL
          AND retention_months IS NOT NULL
          AND {base} IS NOT NULL
          AND {base} < NOW() - (retention_months * INTERVAL '1 month')
        ORDER BY {base} ASC
    """
    )
    result = await db.execute(stmt)
    rows = result.mappings().all()

    archived: list[dict] = []
    now = datetime.now(UTC)
    for row in rows:
        case_id = row["id"]
        retention_base = row["retention_base"]
        archived.append(
            {
                "case_id": str(case_id),
                "title": row["title"],
                "department": row["department"],
                "retention_months": row["retention_months"],
                "retention_base": (
                    retention_base.isoformat() if retention_base else None
                ),
                "completed_at": (
                    row["completed_at"].isoformat() if row["completed_at"] else None
                ),
            }
        )

        if dry_run:
            continue

        case = await db.get(CaseModel, case_id)
        if case is None:
            continue
        case.archived_at = now
        activity = ActivityLogModel(
            case_id=case_id,
            event_type="retention_auto_archived",
            payload={
                "retention_months": case.retention_months,
                "retention_base": (
                    retention_base.isoformat() if retention_base else None
                ),
                "completed_at": (
                    case.completed_at.isoformat() if case.completed_at else None
                ),
                "require_completed": settings.retention_require_completed,
                "archived_by": "system",
            },
        )
        db.add(activity)
        logger.info(
            "Auto-archiving case",
            extra={
                "case_id": str(case_id),
                "retention_months": case.retention_months,
                "retention_base": (
                    retention_base.isoformat() if retention_base else None
                ),
            },
        )

    if not dry_run and archived:
        await db.flush()

    logger.info(
        "Retention scan complete",
        extra={
            "archived": len(archived),
            "dry_run": dry_run,
            "require_completed": settings.retention_require_completed,
        },
    )
    return archived


async def scan_cases_due_for_retention_warning(db: AsyncSession) -> list[dict]:
    """Listet Vorgänge, deren Aufbewahrungsfrist innerhalb von retention_grace_days abläuft.

    Reines Read-only-Scan – markiert oder archiviert keine Vorgänge; dient zur
    Vorab-Information (z. B. Dashboard-Anzeige oder Benachrichtigungs-Task).
    """
    grace = max(0, int(settings.retention_grace_days))
    base = _retention_base_sql()
    stmt = text(
        f"""
        SELECT id, title, department, retention_months, created_at, completed_at,
               {base} AS retention_base,
               ({base} + (retention_months * INTERVAL '1 month')) AS retention_due_at
        FROM cases
        WHERE archived_at IS NULL
          AND retention_months IS NOT NULL
          AND {base} IS NOT NULL
          AND {base} + (retention_months * INTERVAL '1 month') BETWEEN NOW() AND NOW() + (:grace * INTERVAL '1 day')
        ORDER BY retention_due_at ASC
    """
    ).bindparams(grace=grace)
    result = await db.execute(stmt)
    rows = result.mappings().all()
    warnings: list[dict] = []
    for row in rows:
        due = row["retention_due_at"]
        warnings.append(
            {
                "case_id": str(row["id"]),
                "title": row["title"],
                "department": row["department"],
                "retention_months": row["retention_months"],
                "retention_due_at": due.isoformat() if due else None,
                "completed_at": (
                    row["completed_at"].isoformat() if row["completed_at"] else None
                ),
            }
        )
    logger.info(
        "Retention warning scan complete",
        extra={"due_count": len(warnings), "grace_days": grace},
    )
    return warnings
