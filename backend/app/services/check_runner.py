import hashlib
import json
import logging
import time
import uuid
from typing import List
from uuid import UUID

from pydantic import BaseModel, Field

from app.config import settings
from app.core.llm import create_agent, llm_retry_call
from app.core.prompt_security import (
    SYSTEM_PROMPT_SAFETY_PREAMBLE,
    sanitize_prompt_field,
    wrap_untrusted_content,
)
from app.core.request_id import get_request_id
from app.models.schemas import FindingSeverityEnum
from app.services.prompt_template_service import get_active_template, render

# Max chars for a check instruction (playbook requirement text). Defense-in-depth
# even though playbooks are admin-controlled — imported playbooks may be less trusted.
_CHECK_INSTRUCTION_MAX_CHARS = 4000

logger = logging.getLogger(__name__)


def _log_extra() -> dict:
    """Return a dict with the current request_id for structured log records."""
    return {"request_id": get_request_id()}


# ---------------------------------------------------------------------------
# LLM response cache (optional Redis-backed)
# ---------------------------------------------------------------------------

_org_profile_hash_cached: str | None = None


def _org_profile_hash() -> str:
    """Stable hash over the organisation context that influences prompt semantics.

    Included so that two deployments with the same prompt/document text but
    different org profiles cannot share a cache entry. Memoized for the process
    lifetime because these settings are immutable after startup.
    """
    global _org_profile_hash_cached
    if _org_profile_hash_cached is None:
        raw = f"{settings.org_profile}\x00{settings.org_name}"
        _org_profile_hash_cached = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
    return _org_profile_hash_cached


def _cache_key(system_prompt: str, user_content: str, case_id: UUID | None, playbook_revision: str = "") -> str:
    """SHA-256 hash of org+case+model+playbook_revision+system+user prompt as a Redis key.

    Scoping the key by ``org_profile`` and ``case_id`` prevents cross-case or
    cross-tenant cache reuse, which could otherwise leak or poison results when
    two contexts produce the same prompt bytes. The model identifier is
    included so that a model upgrade (e.g. llama3.2 → llama3.3) automatically
    invalidates existing cache entries. ``playbook_revision`` (format
    "<playbook_id>:<version>") ensures a cache miss whenever the playbook
    content changes, so stale LLM responses are never returned after an update.
    """
    model_id = f"{settings.llm_provider}:{settings.ollama_model if settings.llm_provider == 'ollama' else settings.openai_model if settings.llm_provider == 'openai' else settings.anthropic_model}"
    case_part = str(case_id) if case_id is not None else "-"
    raw = f"{_org_profile_hash()}\x00{case_part}\x00{model_id}\x00{playbook_revision}\x00{system_prompt}\x00{user_content}"
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return f"llm_cache:{digest}"


class CheckResult(BaseModel):
    is_compliant: bool = Field(description="True if the check passed, False otherwise.")
    severity: FindingSeverityEnum = Field(description="Severity of the finding if not compliant.")
    description: str = Field(description="Explanation of the finding.")
    evidence: List[str] = Field(description="Quotes from the text supporting the finding.")
    recommendation: str = Field(description="Recommendation to fix the issue.")


# Modul-weiter Redis-Client-Singleton: wird einmalig pro Prozess erstellt und
# wiederverwendet, statt pro Cache-Aufruf eine neue Verbindung aufzubauen.
# Analog zum _async_session_factory-Muster in celery_app.py.
_redis_client = None


def _get_redis_client():
    """Gibt den Modul-Singleton-Redis-Client zurück (lazy init, thread-safe via GIL)."""
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


async def _cache_get(key: str) -> CheckResult | None:
    """Return a cached CheckResult or None if cache is disabled / miss."""
    if not settings.llm_cache_enabled:
        return None
    try:
        r = _get_redis_client()
        if r is None:
            return None
        raw = await r.get(key)
        if raw is None:
            return None
        return CheckResult.model_validate_json(raw)
    except Exception as exc:
        logger.warning("LLM cache GET failed: %s", exc, extra={"cache_key": key})
        return None


async def _cache_set(key: str, result: CheckResult) -> None:
    """Store a CheckResult in Redis with the configured TTL."""
    if not settings.llm_cache_enabled:
        return
    try:
        r = _get_redis_client()
        if r is None:
            return
        await r.setex(key, settings.llm_cache_ttl, result.model_dump_json())
    except Exception as exc:
        logger.warning("LLM cache SET failed: %s", exc, extra={"cache_key": key})

def _context_chars_per_doc() -> int:
    """Return configured per-document character limit for LLM context."""
    return getattr(settings, "max_context_chars_per_doc", 15000)


def _rag_context_chars() -> int:
    """Return configured RAG context character limit."""
    return getattr(settings, "max_context_chars_rag", 20000)



# Per-document character limit for LLM context (single-doc and cross-doc)
# These are module-level defaults; use _context_chars_per_doc() / _rag_context_chars() at call time
# to respect runtime configuration from settings.
CONTEXT_CHARS_PER_DOC = 15000
RAG_CONTEXT_CHARS = 20000

# Built-in defaults when no DB template is active (use same placeholder names as configurable templates)
DEFAULT_CHECK_FULL_TEXT_DOCUMENT_SYSTEM = (
    "You are a strict data protection auditor. Analyze the provided document text against the specific requirement. {language_hint}"
)
DEFAULT_CHECK_FULL_TEXT_DOCUMENT_USER = """{legal_bases_section}Requirement: {requirement}

Document Text:
---
{document_text}
---

Evaluate if the document meets the requirement.
"""
DEFAULT_CHECK_FULL_TEXT_CROSS_SYSTEM = (
    "You are a strict data protection auditor. Analyze the following set of documents "
    "as a whole (e.g. consistency between them, completeness across documents). "
    "Answer based on the combined context and the given requirement. {language_hint}"
)
DEFAULT_CHECK_FULL_TEXT_CROSS_USER = """{legal_bases_section}Requirement: {requirement}

Documents (consider all of them together):
{documents}

Evaluate whether the set of documents meets the requirement (e.g. consistency, completeness).
"""
DEFAULT_CHECK_RAG_DOCUMENT_SYSTEM = (
    "You are a strict data protection auditor. You are given relevant excerpts from a document "
    "(retrieved by semantic search). Analyze these excerpts against the specific requirement. {language_hint}"
)
DEFAULT_CHECK_RAG_DOCUMENT_USER = """{legal_bases_section}Requirement: {requirement}

Relevant document excerpts:
---
{excerpts}
---

Evaluate if the document (based on these excerpts) meets the requirement.
"""
DEFAULT_CHECK_RAG_CROSS_SYSTEM = (
    "You are a strict data protection auditor. You are given relevant excerpts from "
    "multiple documents (retrieved by semantic search). Analyze them as a whole against the requirement. {language_hint}"
)
DEFAULT_CHECK_RAG_CROSS_USER = """{legal_bases_section}Requirement: {requirement}

Relevant excerpts from case documents:
---
{excerpts}
---

Evaluate whether the set of documents (based on these excerpts) meets the requirement.
"""


def _language_hint(language: str | None) -> str:
    """Return a short hint for the LLM (e.g. 'Document/case language: DE. Evaluate in that language.')."""
    if not language or language == "de":
        return "Document/case language: DE. Evaluate and respond in German."
    if language == "en":
        return "Document/case language: EN. Evaluate and respond in English."
    return "Document/case language: DE/EN (mixed or both). Evaluate and respond in the language of the document content."


def _legal_bases_section(legal_bases_context: str | None) -> str:
    """Format optional legal bases context for prompt. Returns empty string if none."""
    if not legal_bases_context or not legal_bases_context.strip():
        return ""
    return "Relevant legal requirements (excerpts from referenced legal bases):\n---\n" + legal_bases_context.strip() + "\n---\n\n"


async def run_check(
    document_text: str,
    check_instruction: str,
    language: str | None = None,
    legal_bases_context: str | None = None,
    *,
    case_id: UUID | None = None,
    playbook_revision: str = "",
) -> CheckResult:
    """Run a single check against a document using the LLM."""
    language_hint = _language_hint(language) if language else ""
    system_tpl = await get_active_template("check_full_text_document_system")
    system = render(system_tpl or DEFAULT_CHECK_FULL_TEXT_DOCUMENT_SYSTEM, {"language_hint": language_hint})
    # Phase 4: tell the model up-front that marker-wrapped content is data.
    system = SYSTEM_PROMPT_SAFETY_PREAMBLE + "\n\n" + system
    user_tpl = await get_active_template("check_full_text_document_user")
    limit = _context_chars_per_doc()
    if document_text and len(document_text) > limit:
        logger.info("Document text truncated: %d → %d chars for check '%s'  [request_id=%s]", len(document_text), limit, check_instruction[:80], get_request_id())
        truncated_text = document_text[:limit] + f"\n\n[... truncated, {len(document_text)} chars total ...]"
    else:
        truncated_text = document_text or ""
    user_content = render(
        user_tpl or DEFAULT_CHECK_FULL_TEXT_DOCUMENT_USER,
        {
            "requirement": sanitize_prompt_field(check_instruction, max_chars=_CHECK_INSTRUCTION_MAX_CHARS),
            "document_text": wrap_untrusted_content(truncated_text, max_chars=limit),
            "legal_bases_section": _legal_bases_section(legal_bases_context),
        },
    )
    agent = create_agent(system_prompt=system)
    cache_key = _cache_key(system, user_content, case_id, playbook_revision)
    cached = await _cache_get(cache_key)
    if cached is not None:
        logger.info("LLM cache hit for check '%s'  [request_id=%s]", check_instruction[:60], get_request_id())
        return cached
    t0 = time.monotonic()
    result = await llm_retry_call(agent, user_content, output_type=CheckResult, request_id=get_request_id())
    elapsed = round(time.monotonic() - t0, 2)
    logger.info(
        "run_check completed: compliant=%s severity=%s elapsed=%.2fs  [request_id=%s]",
        result.output.is_compliant,
        result.output.severity if not result.output.is_compliant else "-",
        elapsed,
        get_request_id(),
    )
    await _cache_set(cache_key, result.output)
    return result.output


async def run_cross_document_check(
    documents: List[tuple[UUID, str]],
    check_instruction: str,
    language: str | None = None,
    legal_bases_context: str | None = None,
    *,
    case_id: UUID | None = None,
    playbook_revision: str = "",
) -> CheckResult:
    """
    Run a single check across multiple documents (case-level / cross-document).
    documents: list of (document_id, extracted_text). Findings from this check
    are persisted with document_id=None.
    """
    language_hint = _language_hint(language) if language else ""
    system_tpl = await get_active_template("check_full_text_cross_system")
    system = render(system_tpl or DEFAULT_CHECK_FULL_TEXT_CROSS_SYSTEM, {"language_hint": language_hint})
    system = SYSTEM_PROMPT_SAFETY_PREAMBLE + "\n\n" + system
    limit = _context_chars_per_doc()
    parts: List[str] = []
    for i, (doc_id, text) in enumerate(documents, 1):
        raw = text or ""
        if len(raw) > limit:
            logger.info("Cross-doc text truncated: %d → %d chars (doc %s)", len(raw), limit, doc_id)
            truncated = raw[:limit] + f"\n[... truncated, {len(raw)} chars total ...]"
        else:
            truncated = raw
        wrapped = wrap_untrusted_content(truncated, max_chars=limit)
        parts.append(f"--- Document {i} (id: {doc_id}) ---\n{wrapped}")
    combined = "\n\n".join(parts)
    user_tpl = await get_active_template("check_full_text_cross_user")
    user_content = render(
        user_tpl or DEFAULT_CHECK_FULL_TEXT_CROSS_USER,
        {
            "requirement": sanitize_prompt_field(check_instruction, max_chars=_CHECK_INSTRUCTION_MAX_CHARS),
            "documents": combined,
            "legal_bases_section": _legal_bases_section(legal_bases_context),
        },
    )
    agent = create_agent(system_prompt=system)
    cache_key = _cache_key(system, user_content, case_id, playbook_revision)
    cached = await _cache_get(cache_key)
    if cached is not None:
        logger.info("LLM cache hit for cross-doc check '%s'  [request_id=%s]", check_instruction[:60], get_request_id())
        return cached
    t0 = time.monotonic()
    result = await llm_retry_call(agent, user_content, output_type=CheckResult, request_id=get_request_id())
    elapsed = round(time.monotonic() - t0, 2)
    logger.info(
        "run_cross_document_check completed: compliant=%s doc_count=%d elapsed=%.2fs  [request_id=%s]",
        result.output.is_compliant,
        len(documents),
        elapsed,
        get_request_id(),
    )
    await _cache_set(cache_key, result.output)
    return result.output


async def run_check_rag(
    document_id: UUID,
    case_id: UUID,
    check_instruction: str,
    language: str | None = None,
    legal_bases_context: str | None = None,
    playbook_revision: str = "",
) -> CheckResult | None:
    """
    Run a single check using RAG: embed check_instruction, retrieve relevant chunks for the document
    from Weaviate, then run the LLM on the assembled context. Returns None if Weaviate/chunks unavailable.
    """
    from app.services.weaviate_service import get_relevant_chunks

    chunks = get_relevant_chunks(document_id, check_instruction, top_k=settings.weaviate_top_k)
    if not chunks:
        return None
    combined = "\n\n---\n\n".join(chunks)
    rag_limit = _rag_context_chars()
    if len(combined) > rag_limit:
        combined = combined[:rag_limit] + "\n\n[... truncated ...]"
    language_hint = _language_hint(language) if language else ""
    system_tpl = await get_active_template("check_rag_document_system")
    system = render(system_tpl or DEFAULT_CHECK_RAG_DOCUMENT_SYSTEM, {"language_hint": language_hint})
    user_tpl = await get_active_template("check_rag_document_user")
    user_content = render(
        user_tpl or DEFAULT_CHECK_RAG_DOCUMENT_USER,
        {
            "requirement": sanitize_prompt_field(check_instruction, max_chars=_CHECK_INSTRUCTION_MAX_CHARS),
            "excerpts": sanitize_prompt_field(combined, max_chars=rag_limit),
            "legal_bases_section": _legal_bases_section(legal_bases_context),
        },
    )
    agent = create_agent(system_prompt=system)
    cache_key = _cache_key(system, user_content, case_id, playbook_revision)
    cached = await _cache_get(cache_key)
    if cached is not None:
        logger.info("LLM cache hit for RAG check '%s'  [request_id=%s]", check_instruction[:60], get_request_id())
        return cached
    t0 = time.monotonic()
    result = await llm_retry_call(agent, user_content, output_type=CheckResult, request_id=get_request_id())
    elapsed = round(time.monotonic() - t0, 2)
    logger.info(
        "run_check_rag completed: compliant=%s doc=%s chunks=%d elapsed=%.2fs  [request_id=%s]",
        result.output.is_compliant,
        document_id,
        len(chunks),
        elapsed,
        get_request_id(),
    )
    await _cache_set(cache_key, result.output)
    return result.output


async def run_cross_document_check_rag(
    case_id: UUID,
    check_instruction: str,
    language: str | None = None,
    legal_bases_context: str | None = None,
    playbook_revision: str = "",
) -> CheckResult | None:
    """
    Run a cross-document check using RAG: retrieve relevant chunks for the case from Weaviate,
    then run the LLM on the assembled context. Returns None if Weaviate/chunks unavailable.
    """
    from app.services.weaviate_service import get_relevant_chunks_for_case

    chunks = get_relevant_chunks_for_case(
        case_id, check_instruction, top_k_per_doc=settings.weaviate_top_k
    )
    if not chunks:
        return None
    combined = "\n\n---\n\n".join(chunks)
    cross_rag_limit = _rag_context_chars()
    if len(combined) > cross_rag_limit:
        combined = combined[:cross_rag_limit] + "\n\n[... truncated ...]"
    language_hint = _language_hint(language) if language else ""
    system_tpl = await get_active_template("check_rag_cross_system")
    system = render(system_tpl or DEFAULT_CHECK_RAG_CROSS_SYSTEM, {"language_hint": language_hint})
    user_tpl = await get_active_template("check_rag_cross_user")
    user_content = render(
        user_tpl or DEFAULT_CHECK_RAG_CROSS_USER,
        {
            "requirement": sanitize_prompt_field(check_instruction, max_chars=_CHECK_INSTRUCTION_MAX_CHARS),
            "excerpts": sanitize_prompt_field(combined, max_chars=cross_rag_limit),
            "legal_bases_section": _legal_bases_section(legal_bases_context),
        },
    )
    agent = create_agent(system_prompt=system)
    cache_key = _cache_key(system, user_content, case_id, playbook_revision)
    cached = await _cache_get(cache_key)
    if cached is not None:
        logger.info("LLM cache hit for cross-RAG check '%s'  [request_id=%s]", check_instruction[:60], get_request_id())
        return cached
    t0 = time.monotonic()
    result = await llm_retry_call(agent, user_content, output_type=CheckResult, request_id=get_request_id())
    elapsed = round(time.monotonic() - t0, 2)
    logger.info(
        "run_cross_document_check_rag completed: compliant=%s case=%s chunks=%d elapsed=%.2fs  [request_id=%s]",
        result.output.is_compliant,
        case_id,
        len(chunks),
        elapsed,
        get_request_id(),
    )
    await _cache_set(cache_key, result.output)
    return result.output
