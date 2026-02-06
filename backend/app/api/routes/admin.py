"""Admin API: read-only settings and connection status (admin role required)."""
from fastapi import APIRouter, Depends

from app.config import settings
from app.core.auth import require_roles
from app.services.connection_checks import check_all_connections

router = APIRouter()


@router.get("/settings")
def get_admin_settings(_user=Depends(require_roles("admin"))):
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
    }


@router.get("/connections")
async def get_connections_status(_user=Depends(require_roles("admin"))):
    """Test connectivity to Ollama, Weaviate, MinIO, Postgres, Redis."""
    return await check_all_connections()
