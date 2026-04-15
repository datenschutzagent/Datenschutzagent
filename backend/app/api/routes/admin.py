"""Admin API: read-only settings, connection status, and user management (admin role required)."""
import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

from app.config import settings
from app.core.auth import require_roles
from app.database import get_db
from app.models.db import UserModel
from app.models.schemas import NotificationTestResponse, RetentionPreviewResponse, RetentionScanResponse, UserResponse
from app.services.connection_checks import check_all_connections

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
        "weaviate_indexing_enabled": getattr(settings, "weaviate_indexing_enabled", False),
        "storage_backend": settings.storage_backend,
        "storage_local_path": settings.storage_local_path if settings.storage_backend == "local" else None,
        "s3_configured": bool(settings.s3_endpoint_url and settings.s3_access_key and settings.s3_secret_key),
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
async def update_user_role(
    user_id: UUID,
    body: UserRoleUpdate,
    db: AsyncSession = Depends(get_db),
    _user=require_roles("admin"),
):
    """Update the role of a user. Allowed roles: viewer, editor, admin."""
    if body.role not in ALLOWED_ROLES:
        raise HTTPException(status_code=400, detail=f"Invalid role '{body.role}'. Allowed: {sorted(ALLOWED_ROLES)}")
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
        extra={"target_user_id": str(user_id), "old_role": old_role, "new_role": body.role},
    )
    return UserResponse.model_validate(user)


# --- Retention Management ---

@router.get("/retention/preview", response_model=RetentionPreviewResponse, summary="Retention-Vorschau (Dry-Run)")
async def retention_preview(
    db: AsyncSession = Depends(get_db),
    _user=require_roles("admin"),
):
    """Zeigt Vorgänge, die beim nächsten Retention-Scan archiviert würden (Dry-Run, keine Änderungen)."""
    from app.services.retention_service import scan_cases_for_retention
    from uuid import UUID as _UUID
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


@router.post("/retention/scan", response_model=RetentionScanResponse, summary="Retention-Scan auslösen")
async def trigger_retention_scan(
    db: AsyncSession = Depends(get_db),
    _user=require_roles("admin"),
):
    """Führt sofort einen Retention-Scan durch und archiviert fällige Vorgänge."""
    logger.info("Admin: manual retention scan triggered")
    from app.services.retention_service import scan_cases_for_retention
    from uuid import UUID as _UUID
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

@router.get("/notifications/test-smtp", response_model=NotificationTestResponse, summary="SMTP-Verbindung testen")
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


@router.post("/notifications/scan-deadlines", summary="Frist-Benachrichtigungen sofort versenden")
async def trigger_deadline_notifications(
    db: AsyncSession = Depends(get_db),
    _user=require_roles("admin"),
):
    """Scannt Fristen und sendet E-Mail-Benachrichtigungen sofort (ohne auf den Celery-Beat-Job zu warten)."""
    logger.info("Admin: manual deadline notification scan triggered")
    from app.services.notification_service import scan_and_notify_deadlines
    result = await scan_and_notify_deadlines(db)
    return result
