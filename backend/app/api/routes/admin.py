"""Admin API: read-only settings, connection status, and user management (admin role required)."""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.auth import require_roles
from app.core.rate_limit import limiter
from app.database import get_db
from app.models.db import UserModel
from app.models.schemas import (
    NotificationTestResponse,
    RetentionPreviewResponse,
    RetentionScanResponse,
    UserResponse,
)
from app.services.connection_checks import check_all_connections

logger = logging.getLogger(__name__)

router = APIRouter()

ALLOWED_ROLES = {"viewer", "editor", "admin"}


class UserRoleUpdate(BaseModel):
    role: str


@router.get("/settings")
def get_admin_settings(_user=require_roles("admin")):
    """Return read-only view of app settings (no secrets)."""
    from app.core.llm import get_llm_provider_info

    return {
        "app_name": settings.app_name,
        "ollama_base_url": settings.ollama_base_url,
        "ollama_enabled": settings.ollama_enabled,
        "ollama_model": settings.ollama_model,
        "weaviate_url": settings.weaviate_url,
        "weaviate_indexing_enabled": getattr(
            settings, "weaviate_indexing_enabled", False
        ),
        "storage_backend": settings.storage_backend,
        "storage_local_path": (
            settings.storage_local_path if settings.storage_backend == "local" else None
        ),
        "s3_configured": bool(
            settings.s3_endpoint_url
            and settings.s3_access_key
            and settings.s3_secret_key
        ),
        "s3_bucket": settings.s3_bucket if settings.s3_endpoint_url else None,
        "celery_enabled": settings.celery_enabled,
        "celery_broker_configured": bool((settings.celery_broker_url or "").strip()),
        "max_context_chars_per_doc": settings.max_context_chars_per_doc,
        "llm_provider": get_llm_provider_info(),
        "smtp_enabled": settings.smtp_enabled,
        "smtp_host": settings.smtp_host if settings.smtp_enabled else None,
        "notification_deadline_warning_days": settings.notification_deadline_warning_days,
        "notification_breach_warning_hours": settings.notification_breach_warning_hours,
        "notification_avv_expiry_warning_days": settings.notification_avv_expiry_warning_days,
    }


@router.get("/connections")
async def get_connections_status(_user=require_roles("admin")):
    """Test connectivity to Ollama, Weaviate, MinIO, Postgres, Redis."""
    return await check_all_connections()


@router.get("/users")
async def list_users(
    db: AsyncSession = Depends(get_db),
    _user=require_roles("admin"),
):
    """List all registered users with their roles."""
    result = await db.execute(select(UserModel).order_by(UserModel.created_at.asc()))
    users = result.scalars().all()
    return [UserResponse.model_validate(u) for u in users]


@router.patch("/users/{user_id}/role")
@limiter.limit("10/minute")
async def update_user_role(
    request: Request,
    user_id: UUID,
    body: UserRoleUpdate,
    db: AsyncSession = Depends(get_db),
    _user=require_roles("admin"),
):
    """Update the role of a user. Allowed roles: viewer, editor, admin."""
    if body.role not in ALLOWED_ROLES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid role '{body.role}'. Allowed: {sorted(ALLOWED_ROLES)}",
        )
    result = await db.execute(select(UserModel).where(UserModel.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    old_role = user.role
    user.role = body.role
    await db.flush()
    await db.refresh(user)
    logger.info(
        "Admin: user role updated",
        extra={
            "target_user_id": str(user_id),
            "old_role": old_role,
            "new_role": body.role,
        },
    )
    return UserResponse.model_validate(user)


# --- Retention Management ---


@router.get(
    "/retention/preview",
    response_model=RetentionPreviewResponse,
    summary="Retention-Vorschau (Dry-Run)",
)
async def retention_preview(
    db: AsyncSession = Depends(get_db),
    _user=require_roles("admin"),
):
    """Zeigt Vorgänge, die beim nächsten Retention-Scan archiviert würden (Dry-Run, keine Änderungen)."""
    from uuid import UUID as _UUID

    from app.services.retention_service import scan_cases_for_retention

    items_raw = await scan_cases_for_retention(db, dry_run=True)
    from app.models.schemas import RetentionPreviewItem

    items = [
        RetentionPreviewItem(
            case_id=_UUID(i["case_id"]),
            title=i["title"],
            department=i["department"],
            retention_months=i["retention_months"],
            updated_at=i["updated_at"],
        )
        for i in items_raw
    ]
    return RetentionPreviewResponse(would_archive_count=len(items), items=items)


@router.post(
    "/retention/scan",
    response_model=RetentionScanResponse,
    summary="Retention-Scan auslösen",
)
@limiter.limit("5/minute")
async def trigger_retention_scan(
    request: Request,
    db: AsyncSession = Depends(get_db),
    _user=require_roles("admin"),
):
    """Führt sofort einen Retention-Scan durch und archiviert fällige Vorgänge."""
    logger.info("Admin: manual retention scan triggered")
    from uuid import UUID as _UUID

    from app.services.retention_service import scan_cases_for_retention

    items_raw = await scan_cases_for_retention(db, dry_run=False)
    from app.models.schemas import RetentionPreviewItem

    items = [
        RetentionPreviewItem(
            case_id=_UUID(i["case_id"]),
            title=i["title"],
            department=i["department"],
            retention_months=i["retention_months"],
            updated_at=i["updated_at"],
        )
        for i in items_raw
    ]
    return RetentionScanResponse(archived_count=len(items), archived=items)


# --- Benachrichtigungs-Test ---


@router.get(
    "/notifications/test-smtp",
    response_model=NotificationTestResponse,
    summary="SMTP-Verbindung testen",
)
def test_smtp(
    _user=require_roles("admin"),
):
    """Testet die SMTP-Verbindung für E-Mail-Benachrichtigungen."""
    from app.services.notification_service import test_smtp_connection

    result = test_smtp_connection()
    return NotificationTestResponse(
        smtp_enabled=settings.smtp_enabled,
        status=result["status"],
        detail=result.get("detail"),
    )


@router.post(
    "/notifications/scan-deadlines", summary="Frist-Benachrichtigungen sofort versenden"
)
@limiter.limit("5/minute")
async def trigger_deadline_notifications(
    request: Request,
    db: AsyncSession = Depends(get_db),
    _user=require_roles("admin"),
):
    """Scannt Fristen und sendet E-Mail-Benachrichtigungen sofort (ohne auf den Celery-Beat-Job zu warten)."""
    logger.info("Admin: manual deadline notification scan triggered")
    from app.services.notification_service import scan_and_notify_deadlines

    result = await scan_and_notify_deadlines(db)
    return result


@router.post(
    "/notifications/scan-critical-findings",
    summary="Benachrichtigungen für neue CRITICAL/HIGH-Findings versenden",
)
@limiter.limit("5/minute")
async def trigger_critical_finding_notifications(
    request: Request,
    db: AsyncSession = Depends(get_db),
    _user=require_roles("admin"),
):
    """Scannt offene Findings mit Schwere CRITICAL/HIGH und informiert den
    jeweiligen Case-Assignee (Cooldown 20h, User-Master-Switch wird beachtet)."""
    logger.info("Admin: manual critical-findings notification scan triggered")
    from app.services.notification_service import scan_and_notify_critical_findings

    return await scan_and_notify_critical_findings(db)


@router.post(
    "/notifications/scan-maturity-decline",
    summary="Admin-Warnung bei signifikantem Compliance-Reife-Rückgang",
)
@limiter.limit("5/minute")
async def trigger_maturity_decline_notifications(
    request: Request,
    db: AsyncSession = Depends(get_db),
    _user=require_roles("admin"),
):
    """Triggert einen Vergleich des aktuellen Composite-Scores gegen den
    Snapshot vor `risk_velocity.window_days` Tagen. Bei Rückgängen ≥ der
    Signifikanz-Schwelle wird eine E-Mail an alle aktiven Admin-Nutzer
    versendet."""
    logger.info("Admin: manual maturity-decline notification scan triggered")
    from app.services.notification_service import scan_and_notify_maturity_decline

    return await scan_and_notify_maturity_decline(db)


# --- Risk-Config Management (Phase C / Item 13) -----------------------------


class RiskConfigUpdateRequest(BaseModel):
    """Body for PUT /admin/risk-config — `config` is validated server-side."""

    config: dict


@router.get("/risk-config", summary="Aktive Risk-Config inkl. Profilpfad abrufen")
def get_admin_risk_config(
    _user=require_roles("viewer", "editor", "admin"),
):
    """Gibt die aktuell geladene Risk-Config zurück (inkl. Profil, YAML-Pfad
    und ob es sich um Defaults handelt). Lesen darf jeder mit App-Zugang.
    """
    from app.services.risk_config_loader import (
        get_risk_config,
        resolve_risk_config_path,
    )

    cfg = get_risk_config()
    path = resolve_risk_config_path(settings)
    return {
        "config": cfg.model_dump(mode="json"),
        "profile": (settings.org_profile or "default").strip() or "default",
        "path": str(path) if path else None,
        "is_default": path is None,
    }


@router.put("/risk-config", summary="Risk-Config persistieren (YAML mit Backup)")
@limiter.limit("10/minute")
async def update_admin_risk_config(
    request: Request,
    body: RiskConfigUpdateRequest,
    _user=require_roles("admin"),
):
    """Validiert die übergebene Config, persistiert sie als YAML
    (vorheriger Stand als .bak.{timestamp} gesichert) und invalidiert
    den LRU-Cache. Bei ungültigem Schema → 422.
    """
    from pydantic import ValidationError as _PydanticValidationError

    from app.services.risk_config_loader import (
        RiskConfig,
        resolve_risk_config_path,
        save_risk_config,
    )

    try:
        cfg = RiskConfig.model_validate(body.config)
    except _PydanticValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors()) from exc

    try:
        path = save_risk_config(cfg)
    except OSError as exc:
        logger.error("Failed to persist risk_config: %s", exc)
        raise HTTPException(
            status_code=500, detail=f"Failed to write risk_config: {exc}"
        ) from exc

    logger.info(
        "Admin: risk_config updated",
        extra={"path": str(path), "profile": settings.org_profile},
    )
    return {
        "config": cfg.model_dump(mode="json"),
        "profile": (settings.org_profile or "default").strip() or "default",
        "path": str(resolve_risk_config_path(settings)),
        "is_default": False,
    }


@router.post("/risk-config/reload", summary="Risk-Config-Cache invalidieren")
def reload_admin_risk_config(
    _user=require_roles("admin"),
):
    """Nützlich, wenn das YAML extern geändert wurde — leert den LRU-Cache,
    damit die nächste Anfrage die Datei neu lädt.
    """
    from app.services.risk_config_loader import reload_risk_config

    reload_risk_config()
    logger.info("Admin: risk_config cache reloaded")
    return {"reloaded": True}


@router.post("/risk-config/preview", summary="Risk-Config Dry-Run gegen Beispieldaten")
@limiter.limit("20/minute")
async def preview_admin_risk_config(
    request: Request,
    body: RiskConfigUpdateRequest,
    _user=require_roles("admin"),
):
    """Berechnet vorher/nachher-Vergleiche für ein paar synthetische
    Beispiel-Cases — komplett ohne LLM-Aufrufe und ohne die echte
    Konfiguration zu verändern.
    """
    from pydantic import ValidationError as _PydanticValidationError

    from app.services.risk_config_loader import RiskConfig, get_risk_config

    try:
        new_cfg = RiskConfig.model_validate(body.config)
    except _PydanticValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors()) from exc

    current_cfg = get_risk_config()

    # Synthetische Inputs für vorher/nachher-Vergleich.
    samples = []

    # Sample 1: AVV mit avg=2.0
    samples.append(
        {
            "name": "AVV-Risikobewertung (avg=2.0 auf 1-5)",
            "inputs": {"avg_score": 2.0},
            "current": {
                "level": current_cfg.avv.level_for_score(2.0),
                "score_pct": current_cfg.avv.normalize_to_percent(2.0),
            },
            "preview": {
                "level": new_cfg.avv.level_for_score(2.0),
                "score_pct": new_cfg.avv.normalize_to_percent(2.0),
            },
        }
    )

    # Sample 2: AVV mit avg=3.5
    samples.append(
        {
            "name": "AVV-Risikobewertung (avg=3.5 auf 1-5)",
            "inputs": {"avg_score": 3.5},
            "current": {
                "level": current_cfg.avv.level_for_score(3.5),
                "score_pct": current_cfg.avv.normalize_to_percent(3.5),
            },
            "preview": {
                "level": new_cfg.avv.level_for_score(3.5),
                "score_pct": new_cfg.avv.normalize_to_percent(3.5),
            },
        }
    )

    # Sample 3: Case-Score mit 2 critical, 3 high
    def _case_score(cfg, c, h, m):
        w = cfg.case_score.severity_weights
        penalty = (
            c * w.get("critical", 0) + h * w.get("high", 0) + m * w.get("medium", 0)
        )
        return min(cfg.case_score.max_score, penalty)

    samples.append(
        {
            "name": "Case-Score (2 critical + 3 high + 5 medium)",
            "inputs": {"critical": 2, "high": 3, "medium": 5},
            "current": {"score": _case_score(current_cfg, 2, 3, 5)},
            "preview": {"score": _case_score(new_cfg, 2, 3, 5)},
        }
    )

    # Sample 4: DSFA-Screening mit 2 erfüllten Standard-Faktoren
    samples.append(
        {
            "name": "DSFA-Screening (2 Faktoren, je Gewicht aus Config)",
            "inputs": {"matched_factors": 2},
            "current": {
                "threshold": current_cfg.dsfa_screening.required_threshold,
                "required": current_cfg.dsfa_screening.required_threshold <= 2.0,
            },
            "preview": {
                "threshold": new_cfg.dsfa_screening.required_threshold,
                "required": new_cfg.dsfa_screening.required_threshold <= 2.0,
            },
        }
    )

    # Sample 5: DSFA-Matrix Lookup für (3, 4)
    samples.append(
        {
            "name": "DSFA-Matrix (Likelihood=3, Severity=4)",
            "inputs": {"likelihood": 3, "severity": 4},
            "current": {"risk_level": current_cfg.dsfa_assessment.risk_level_for(3, 4)},
            "preview": {"risk_level": new_cfg.dsfa_assessment.risk_level_for(3, 4)},
        }
    )

    # Sample 6: Velocity-Score (Median 25 Tage)
    def _vel(cfg):
        from app.services.analytics_service import _velocity_score

        return round(
            _velocity_score(
                25.0,
                cfg.maturity.velocity.optimal_days,
                cfg.maturity.velocity.worst_days,
            ),
            1,
        )

    samples.append(
        {
            "name": "Velocity-Score (Median 25 Tage)",
            "inputs": {"median_days": 25},
            "current": {"velocity_score": _vel(current_cfg)},
            "preview": {"velocity_score": _vel(new_cfg)},
        }
    )

    return {"samples": samples}
