"""Load and render versioned prompt templates from DB. Used by check_runner and vvt_service."""
from __future__ import annotations

import re
from typing import Any

from sqlalchemy import select

from app.database import async_session_factory
from app.models.db import PromptTemplateModel

# All prompt template keys and their metadata (for API/frontend).
PROMPT_TEMPLATE_KEY_META: list[dict[str, Any]] = [
    {"key": "check_full_text_document_system", "description": "Einzeldokument, Full-Text, System", "placeholders": ["language_hint"]},
    {"key": "check_full_text_document_user", "description": "Einzeldokument, Full-Text, User", "placeholders": ["requirement", "document_text"]},
    {"key": "check_full_text_cross_system", "description": "Vorgang, Full-Text, System", "placeholders": ["language_hint"]},
    {"key": "check_full_text_cross_user", "description": "Vorgang, Full-Text, User", "placeholders": ["requirement", "documents"]},
    {"key": "check_rag_document_system", "description": "Einzeldokument, RAG, System", "placeholders": ["language_hint"]},
    {"key": "check_rag_document_user", "description": "Einzeldokument, RAG, User", "placeholders": ["requirement", "excerpts"]},
    {"key": "check_rag_cross_system", "description": "Vorgang, RAG, System", "placeholders": ["language_hint"]},
    {"key": "check_rag_cross_user", "description": "Vorgang, RAG, User", "placeholders": ["requirement", "excerpts"]},
    {"key": "vvt_system", "description": "VVT-Normalisierung, System", "placeholders": ["language_hint"]},
    {"key": "vvt_user", "description": "VVT-Normalisierung, User", "placeholders": ["field_list", "document_text"]},
]
VALID_PROMPT_KEYS: set[str] = {m["key"] for m in PROMPT_TEMPLATE_KEY_META}


# In-memory cache: key -> content. Cleared on create/update (API calls invalidate).
_cache: dict[str, str] = {}
_CACHE_KEY_PREFIX = "prompt:"


def _cache_key(key: str) -> str:
    return f"{_CACHE_KEY_PREFIX}{key}"


def invalidate_cache(key: str | None = None) -> None:
    """Invalidate cached template(s). key=None clears all."""
    if key is None:
        _cache.clear()
    else:
        _cache.pop(_cache_key(key), None)


async def get_active_template(key: str) -> str | None:
    """
    Load the active template content for the given key from DB.
    Returns None if no active version exists. Uses a simple in-memory cache.
    """
    ck = _cache_key(key)
    if ck in _cache:
        return _cache[ck]
    async with async_session_factory() as session:
        result = await session.execute(
            select(PromptTemplateModel.content).where(
                PromptTemplateModel.key == key,
                PromptTemplateModel.is_active.is_(True),
            ).limit(1)
        )
        content = result.scalar_one_or_none()
        if content is None:
            return None
        _cache[ck] = content
        return content


def render(template_content: str, placeholders: dict[str, Any]) -> str:
    """
    Replace {name} in template_content with placeholders.get("name", "").
    Values are coerced to str.
    """
    out = template_content
    for name, value in placeholders.items():
        placeholder = "{" + name + "}"
        out = out.replace(placeholder, str(value) if value is not None else "")
    # Replace any remaining {xxx} with empty string so unknown placeholders don't leak
    out = re.sub(r"\{[a-zA-Z_]+\}", "", out)
    return out
