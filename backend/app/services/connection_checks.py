"""Check connectivity to Ollama, Weaviate, MinIO/S3, Postgres, Redis. Used by admin connections API."""
import logging
import urllib.request
from typing import Any

from sqlalchemy import text

from app.config import settings
from app.database import engine

logger = logging.getLogger(__name__)


async def check_ollama() -> dict[str, Any]:
    """Return status and optional message for Ollama."""
    if not settings.ollama_enabled:
        return {"status": "disabled", "message": "Ollama is disabled"}
    base = (settings.ollama_base_url or "").rstrip("/")
    if not base:
        return {"status": "unreachable", "message": "Ollama URL not set"}
    try:
        req = urllib.request.Request(f"{base}/api/tags", method="GET")
        with urllib.request.urlopen(req, timeout=3) as resp:
            if resp.status == 200:
                return {"status": "ok"}
    except Exception as e:
        logger.debug("Ollama connection check failed: %s", e)
        return {"status": "unreachable", "message": str(e)}
    return {"status": "unreachable", "message": "Unknown error"}


async def check_weaviate() -> dict[str, Any]:
    """Return status and optional message for Weaviate."""
    if not getattr(settings, "weaviate_indexing_enabled", False):
        return {"status": "disabled", "message": "Weaviate indexing is disabled"}
    url = (settings.weaviate_url or "").strip().rstrip("/")
    if not url:
        return {"status": "unreachable", "message": "Weaviate URL not set"}
    try:
        req = urllib.request.Request(f"{url}/v1/.well-known/ready", method="GET")
        with urllib.request.urlopen(req, timeout=3) as resp:
            if resp.status == 200:
                return {"status": "ok"}
    except Exception as e:
        logger.debug("Weaviate connection check failed: %s", e)
        return {"status": "unreachable", "message": str(e)}
    return {"status": "unreachable", "message": "Unknown error"}


async def check_minio() -> dict[str, Any]:
    """Return status and optional message for MinIO/S3."""
    if settings.storage_backend != "minio":
        return {"status": "not_configured", "message": "Storage backend is not MinIO/S3"}
    if not settings.s3_endpoint_url:
        return {"status": "not_configured", "message": "S3 endpoint not set"}
    try:
        from app.storage import _get_minio_client
        client = _get_minio_client()
        client.list_buckets()
        return {"status": "ok"}
    except Exception as e:
        logger.debug("MinIO connection check failed: %s", e)
        return {"status": "unreachable", "message": str(e)}


async def check_postgres() -> dict[str, Any]:
    """Return status and optional message for Postgres."""
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return {"status": "ok"}
    except Exception as e:
        logger.debug("Postgres connection check failed: %s", e)
        return {"status": "unreachable", "message": str(e)}


def _check_redis_sync() -> dict[str, Any]:
    """Synchronous Redis check (redis client is sync)."""
    url = (settings.celery_broker_url or "").strip()
    if not url or not url.startswith("redis"):
        return {"status": "not_configured", "message": "Redis broker URL not set"}
    try:
        import redis
        r = redis.Redis.from_url(url)
        r.ping()
        return {"status": "ok"}
    except Exception as e:
        logger.debug("Redis connection check failed: %s", e)
        return {"status": "unreachable", "message": str(e)}


async def check_redis() -> dict[str, Any]:
    """Return status and optional message for Redis (run in thread to avoid blocking)."""
    import asyncio
    return await asyncio.to_thread(_check_redis_sync)


async def check_all_connections() -> dict[str, Any]:
    """Run all connection checks and return a dict keyed by service name."""
    import asyncio
    results = await asyncio.gather(
        check_ollama(),
        check_weaviate(),
        check_minio(),
        check_postgres(),
        check_redis(),
        return_exceptions=True,
    )
    out = {}
    for key, res in zip(
        ["ollama", "weaviate", "minio", "postgres", "redis"],
        results,
    ):
        if isinstance(res, Exception):
            out[key] = {"status": "unreachable", "message": str(res)}
        else:
            out[key] = res
    return out
