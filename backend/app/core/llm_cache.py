"""Redis-backed LLM response cache (optional, keyed by org+case+model+prompt hash).

Extracted from check_runner.py so the caching infrastructure is reusable across
services and testable in isolation.
"""

import hashlib
import logging
from typing import TypeVar
from uuid import UUID

from pydantic import BaseModel

from app.config import settings
from app.core.llm import get_active_model_name

logger = logging.getLogger(__name__)

M = TypeVar("M", bound=BaseModel)

# ---------------------------------------------------------------------------
# Org-profile hash (memoized for process lifetime — settings are immutable post-startup)
# ---------------------------------------------------------------------------

_org_profile_hash_cached: str | None = None


def _org_profile_hash() -> str:
    """Stable hash over the organisation context that influences prompt semantics.

    Included so that two deployments with the same prompt/document text but
    different org profiles cannot share a cache entry.
    """
    global _org_profile_hash_cached
    if _org_profile_hash_cached is None:
        raw = f"{settings.org_profile}\x00{settings.org_name}"
        _org_profile_hash_cached = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
    return _org_profile_hash_cached


def _cache_key(
    system_prompt: str,
    user_content: str,
    case_id: UUID | None,
    playbook_revision: str = "",
) -> str:
    """SHA-256 hash of org+case+model+playbook_revision+system+user prompt as a Redis key.

    Scoping the key by ``org_profile`` and ``case_id`` prevents cross-case or
    cross-tenant cache reuse. The model identifier is included so that a model
    upgrade automatically invalidates existing cache entries. ``playbook_revision``
    (format "<playbook_id>:<version>") ensures a cache miss whenever the playbook
    content changes.
    """
    model_id = f"{settings.llm_provider}:{get_active_model_name()}:{settings.llm_structured_output_mode}"
    case_part = str(case_id) if case_id is not None else "-"
    raw = f"{_org_profile_hash()}\x00{case_part}\x00{model_id}\x00{playbook_revision}\x00{system_prompt}\x00{user_content}"
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return f"llm_cache:{digest}"


# ---------------------------------------------------------------------------
# Redis connection singleton
# ---------------------------------------------------------------------------

_redis_client = None


def _get_redis_client():
    """Return the module-singleton Redis client (lazy init, thread-safe via GIL)."""
    global _redis_client
    if _redis_client is None:
        try:
            import redis.asyncio as aioredis  # type: ignore

            _redis_client = aioredis.from_url(
                settings.celery_broker_url,
                decode_responses=True,
                max_connections=10,
            )
        except Exception as exc:
            logger.debug("Redis client init failed (cache disabled): %s", exc)
    return _redis_client


# ---------------------------------------------------------------------------
# Cache get/set
# ---------------------------------------------------------------------------


async def _cache_get(key: str, model_class: type[M]) -> M | None:  # noqa: UP047
    """Return a cached Pydantic model or None if cache is disabled / miss."""
    if not settings.llm_cache_enabled:
        return None
    try:
        r = _get_redis_client()
        if r is None:
            return None
        raw = await r.get(key)
        if raw is None:
            return None
        return model_class.model_validate_json(raw)
    except Exception as exc:
        logger.warning("LLM cache GET failed: %s", exc, extra={"cache_key": key})
        return None


async def _cache_set(key: str, result: BaseModel) -> None:
    """Store a Pydantic model in Redis with the configured TTL."""
    if not settings.llm_cache_enabled:
        return
    try:
        r = _get_redis_client()
        if r is None:
            return
        await r.setex(key, settings.llm_cache_ttl, result.model_dump_json())
    except Exception as exc:
        logger.warning("LLM cache SET failed: %s", exc, extra={"cache_key": key})
