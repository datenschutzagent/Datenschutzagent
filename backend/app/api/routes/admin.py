"""Admin API: read-only settings, connection status, and user management (admin role required)."""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.auth import require_roles
from app.database import get_db
from app.models.db import UserModel, orm_to_user_response
from app.services.connection_checks import check_all_connections

router = APIRouter()

ALLOWED_ROLES = {"viewer", "editor", "admin"}


class UserRoleUpdate(BaseModel):
    role: str


@router.get("/settings")
def get_admin_settings(_user=require_roles("admin")):
    """Return read-only view of app settings (no secrets)."""
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
    return [orm_to_user_response(u) for u in users]


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
    user.role = body.role
    await db.flush()
    await db.refresh(user)
    return orm_to_user_response(user)
