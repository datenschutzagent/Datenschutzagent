import hashlib
import json
import logging
import time
import uuid
from typing import List
from uuid import UUID

from pydantic import BaseModel, Field
from pydantic_ai import ModelRetry

from app.config import settings
from app.core.grounding import grounding_ratio, partition_grounded
from app.core.llm import create_agent, llm_retry_call
from app.core.prompt_security import (
    SYSTEM_PROMPT_SAFETY_PREAMBLE,
    sanitize_prompt_field,
    wrap_untrusted_content,
)
from app.core.request_id import get_request_id
from app.models.schemas import FindingSeverityEnum
from app.services.document_processor import detect_language
from app.services.prompt_template_service import get_active_template, render
from app.services.weaviate_service import chunk_text, truncate_sentence_aware

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
    reasoning: str = Field(
        default="",
        description="Brief step-by-step reasoning that leads to the verdict. Fill this FIRST, "
        "before deciding is_compliant/severity, so the verdict follows from the analysis.",
    )
    is_compliant: bool = Field(description="True if the check passed, False otherwise.")
    severity: FindingSeverityEnum = Field(description="Severity of the finding if not compliant.")
    description: str = Field(description="Explanation of the finding.")
    evidence: List[str] = Field(description="Verbatim quotes from the document supporting the finding.")
    recommendation: str = Field(description="Recommendation to fix the issue.")
    confidence: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="Self-assessed confidence (0=unsure, 1=certain). Low confidence is acceptable "
        "when the document is incomplete or ambiguous.",
    )


# Appended to every check system prompt so verdicts are consistent and verifiable:
# a severity rubric (the model otherwise has no definition of low/medium/high/critical),
# a verbatim-evidence rule (so quotes can be grounded against the source), and a request
# for a calibrated confidence.
CHECK_OUTPUT_GUIDANCE = (
    "\n\nSeverity rubric for non-compliant findings:\n"
    "- critical: unlawful processing or a violation that can cause serious harm to data subjects "
    "(e.g. missing legal basis, unsafeguarded third-country transfer, special-category data exposed).\n"
    "- high: a clear legal requirement is unmet with material risk (e.g. missing retention period, "
    "no AVV for a processor).\n"
    "- medium: a relevant gap or inconsistency with limited risk.\n"
    "- low: a minor or formal deficiency.\n"
    "- info: an observation without a compliance defect.\n"
    "For compliant results use severity 'info'.\n"
    "Evidence MUST be verbatim quotes copied from the provided document — never paraphrase or "
    "invent quotes. If you cannot quote supporting text, return an empty evidence list.\n"
    "Set confidence (0.0-1.0) to reflect how certain you are given the available text."
)


def _make_grounding_validator(source_text: str):
    """Build a Pydantic AI output validator that requests self-correction on inconsistent output.

    Enforces two things via ``ModelRetry`` (which lets the model self-correct within the
    configured ``output_retries`` budget, never hard-failing on the final attempt):

    1. Schema consistency — a compliant verdict must use severity 'info'; a non-compliant
       verdict must use a real severity and carry a non-empty recommendation.
    2. Evidence grounding — in the egregious case of a non-compliant verdict whose every quote
       is ungrounded, ask the model to quote verbatim or return no evidence.

    Quote pruning + confidence adjustment still happens in :func:`_apply_grounding` afterwards.
    """
    def _validate(ctx, output: CheckResult) -> CheckResult:
        # Schema consistency (cheap, deterministic). Skip on the final allowed attempt so a
        # stubborn model never hard-fails the pipeline.
        if ctx.retry < settings.llm_output_retries:
            if output.is_compliant and output.severity != "info":
                raise ModelRetry("A compliant result (is_compliant=true) must use severity 'info'.")
            if not output.is_compliant:
                if output.severity == "info":
                    raise ModelRetry(
                        "A non-compliant result (is_compliant=false) must use a real severity "
                        "(low/medium/high/critical), not 'info'."
                    )
                if not (output.recommendation or "").strip():
                    raise ModelRetry(
                        "A non-compliant result must include a non-empty recommendation describing "
                        "how to fix the issue."
                    )
        if not settings.evidence_grounding_enabled:
            return output
        if (
            not output.is_compliant
            and output.evidence
            and source_text
            and source_text.strip()
            and ctx.retry < settings.llm_output_retries
        ):
            ratio = grounding_ratio(output.evidence, source_text, settings.evidence_grounding_threshold)
            if ratio == 0.0:
                raise ModelRetry(
                    "None of the evidence quotes appear in the provided document. "
                    "Quote ONLY text that appears verbatim in the document, or return an empty "
                    "evidence list if you cannot."
                )
        return output

    return _validate


def _apply_grounding(result: CheckResult, source_text: str) -> CheckResult:
    """Drop ungrounded (hallucinated) evidence quotes and lower confidence accordingly."""
    if not settings.evidence_grounding_enabled or not result.evidence:
        return result
    if not source_text or not source_text.strip():
        return result
    grounded, ungrounded = partition_grounded(
        result.evidence, source_text, settings.evidence_grounding_threshold
    )
    if ungrounded:
        total = len(grounded) + len(ungrounded)
        penalty = len(ungrounded) / total if total else 0.0
        result.evidence = grounded
        result.confidence = round(max(0.0, result.confidence * (1.0 - 0.5 * penalty)), 2)
        logger.warning(
            "Grounding dropped %d/%d ungrounded evidence quote(s); confidence→%.2f  [request_id=%s]",
            len(ungrounded), total, result.confidence, get_request_id(),
        )
    return result


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


# Severity ordering for aggregating map-reduce results (higher = worse).
_SEVERITY_RANK = {"info": 0, "low": 1, "medium": 2, "high": 3, "critical": 4}

# Appended to the system prompt when a check runs over a document fragment (map-reduce), so
# the model judges only the fragment and does not flag merely-absent information as a violation.
_FRAGMENT_SYSTEM_SUFFIX = (
    "\n\nNOTE: You are seeing ONE fragment of a larger document. Judge only what is present "
    "in this fragment. Report non-compliant ONLY if this fragment actively contradicts or "
    "violates the requirement. If the relevant information is simply not in this fragment, "
    "treat it as compliant (info) — it may appear elsewhere in the document."
)


# Re-exported for callers/tests; canonical implementation lives in weaviate_service.
_truncate_sentence_aware = truncate_sentence_aware


def _build_context_windows(text: str, limit: int, max_windows: int) -> list[str]:
    """Group sentence-aware chunks into <= max_windows windows of up to ``limit`` chars each."""
    windows: list[str] = []
    current = ""
    for chunk in chunk_text(text or ""):
        if current and len(current) + len(chunk) + 2 > limit:
            windows.append(current)
            current = chunk
            if len(windows) >= max_windows:
                return windows
        else:
            current = f"{current}\n\n{chunk}" if current else chunk
    if current and len(windows) < max_windows:
        windows.append(current)
    return windows[:max_windows]


def _aggregate_check_results(results: list[CheckResult]) -> CheckResult:
    """Combine per-fragment results: any active violation wins (strict auditor)."""
    non_compliant = [r for r in results if not r.is_compliant]
    if non_compliant:
        worst = max(non_compliant, key=lambda r: _SEVERITY_RANK.get(r.severity, 0))
        merged_evidence: list[str] = []
        for r in non_compliant:
            for q in r.evidence:
                if q not in merged_evidence:
                    merged_evidence.append(q)
        return CheckResult(
            reasoning=worst.reasoning,
            is_compliant=False,
            severity=worst.severity,
            description=worst.description,
            evidence=merged_evidence,
            recommendation=worst.recommendation,
            confidence=round(min(r.confidence for r in results), 2),
        )
    # All fragments compliant.
    base = results[0]
    return CheckResult(
        reasoning=base.reasoning,
        is_compliant=True,
        severity="info",
        description=base.description,
        evidence=base.evidence,
        recommendation=base.recommendation,
        confidence=round(min(r.confidence for r in results), 2),
    )


async def _llm_check_call(
    *,
    system: str,
    user_content: str,
    source_text: str,
    case_id: UUID | None,
    playbook_revision: str,
    label: str,
) -> CheckResult:
    """Shared single check call: cache lookup → grounded LLM run → cache store."""
    agent = create_agent(
        system_prompt=system,
        output_validator=_make_grounding_validator(source_text),
    )
    cache_key = _cache_key(system, user_content, case_id, playbook_revision)
    cached = await _cache_get(cache_key)
    if cached is not None:
        logger.info("LLM cache hit for check '%s'  [request_id=%s]", label[:60], get_request_id())
        return cached
    result = await llm_retry_call(agent, user_content, output_type=CheckResult, request_id=get_request_id())
    out = _apply_grounding(result.output, source_text)
    await _cache_set(cache_key, out)
    return out


async def run_check(
    document_text: str,
    check_instruction: str,
    language: str | None = None,
    legal_bases_context: str | None = None,
    *,
    case_id: UUID | None = None,
    playbook_revision: str = "",
) -> CheckResult:
    """Run a single check against a document using the LLM.

    For documents longer than the per-doc context limit, the check runs over sentence-aware
    fragments (map-reduce) and the results are aggregated, instead of silently truncating to
    the first N characters (which can hide non-compliance beyond the cut-off).
    """
    # Auto-detect the document language when the caller did not specify one, so the LLM is asked to
    # evaluate/respond in the document's language instead of defaulting to German.
    language = language or detect_language(document_text)
    language_hint = _language_hint(language) if language else ""
    system_tpl = await get_active_template("check_full_text_document_system")
    system = render(system_tpl or DEFAULT_CHECK_FULL_TEXT_DOCUMENT_SYSTEM, {"language_hint": language_hint})
    # Phase 4: tell the model up-front that marker-wrapped content is data.
    system = SYSTEM_PROMPT_SAFETY_PREAMBLE + "\n\n" + system + CHECK_OUTPUT_GUIDANCE
    user_tpl = await get_active_template("check_full_text_document_user")
    limit = _context_chars_per_doc()
    requirement = sanitize_prompt_field(check_instruction, max_chars=_CHECK_INSTRUCTION_MAX_CHARS)
    legal_section = _legal_bases_section(legal_bases_context)
    t0 = time.monotonic()

    over_limit = bool(document_text) and len(document_text) > limit
    if over_limit and getattr(settings, "long_doc_map_reduce_enabled", True):
        windows = _build_context_windows(document_text, limit, getattr(settings, "long_doc_max_chunks", 6))
        logger.info(
            "Long document (%d chars) → map-reduce over %d fragments for check '%s'  [request_id=%s]",
            len(document_text), len(windows), check_instruction[:80], get_request_id(),
        )
        frag_system = system + _FRAGMENT_SYSTEM_SUFFIX
        results: list[CheckResult] = []
        for window in windows:
            user_content = render(
                user_tpl or DEFAULT_CHECK_FULL_TEXT_DOCUMENT_USER,
                {
                    "requirement": requirement,
                    "document_text": wrap_untrusted_content(window, max_chars=limit),
                    "legal_bases_section": legal_section,
                },
            )
            results.append(await _llm_check_call(
                system=frag_system, user_content=user_content, source_text=window,
                case_id=case_id, playbook_revision=playbook_revision, label=check_instruction,
            ))
        out = _aggregate_check_results(results) if results else CheckResult(
            is_compliant=True, severity="info", description="No content to evaluate.",
            evidence=[], recommendation="", confidence=0.3,
        )
    else:
        truncated_text, truncated = _truncate_sentence_aware(document_text or "", limit)
        user_content = render(
            user_tpl or DEFAULT_CHECK_FULL_TEXT_DOCUMENT_USER,
            {
                "requirement": requirement,
                "document_text": wrap_untrusted_content(truncated_text, max_chars=limit),
                "legal_bases_section": legal_section,
            },
        )
        out = await _llm_check_call(
            system=system, user_content=user_content, source_text=truncated_text,
            case_id=case_id, playbook_revision=playbook_revision, label=check_instruction,
        )
        if truncated:
            out.confidence = round(out.confidence * 0.9, 2)  # partial context → less certain

    elapsed = round(time.monotonic() - t0, 2)
    logger.info(
        "run_check completed: compliant=%s severity=%s confidence=%.2f elapsed=%.2fs  [request_id=%s]",
        out.is_compliant,
        out.severity if not out.is_compliant else "-",
        out.confidence,
        elapsed,
        get_request_id(),
    )
    return out


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
    if not language and documents:
        language = detect_language(documents[0][1])
    language_hint = _language_hint(language) if language else ""
    system_tpl = await get_active_template("check_full_text_cross_system")
    system = render(system_tpl or DEFAULT_CHECK_FULL_TEXT_CROSS_SYSTEM, {"language_hint": language_hint})
    system = SYSTEM_PROMPT_SAFETY_PREAMBLE + "\n\n" + system + CHECK_OUTPUT_GUIDANCE
    limit = _context_chars_per_doc()
    parts: list[str] = []
    source_parts: list[str] = []
    for i, (doc_id, text) in enumerate(documents, 1):
        truncated, was_truncated = _truncate_sentence_aware(text or "", limit)
        if was_truncated:
            logger.info("Cross-doc text truncated: %d → ~%d chars (doc %s)", len(text or ""), limit, doc_id)
        wrapped = wrap_untrusted_content(truncated, max_chars=limit)
        parts.append(f"--- Document {i} (id: {doc_id}) ---\n{wrapped}")
        source_parts.append(truncated)
    combined = "\n\n".join(parts)
    source_text = "\n\n".join(source_parts)
    user_tpl = await get_active_template("check_full_text_cross_user")
    user_content = render(
        user_tpl or DEFAULT_CHECK_FULL_TEXT_CROSS_USER,
        {
            "requirement": sanitize_prompt_field(check_instruction, max_chars=_CHECK_INSTRUCTION_MAX_CHARS),
            "documents": combined,
            "legal_bases_section": _legal_bases_section(legal_bases_context),
        },
    )
    t0 = time.monotonic()
    out = await _llm_check_call(
        system=system, user_content=user_content, source_text=source_text,
        case_id=case_id, playbook_revision=playbook_revision, label=check_instruction,
    )
    elapsed = round(time.monotonic() - t0, 2)
    logger.info(
        "run_cross_document_check completed: compliant=%s doc_count=%d confidence=%.2f elapsed=%.2fs  [request_id=%s]",
        out.is_compliant,
        len(documents),
        out.confidence,
        elapsed,
        get_request_id(),
    )
    return out


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
    system = system + CHECK_OUTPUT_GUIDANCE
    user_tpl = await get_active_template("check_rag_document_user")
    user_content = render(
        user_tpl or DEFAULT_CHECK_RAG_DOCUMENT_USER,
        {
            "requirement": sanitize_prompt_field(check_instruction, max_chars=_CHECK_INSTRUCTION_MAX_CHARS),
            "excerpts": sanitize_prompt_field(combined, max_chars=rag_limit),
            "legal_bases_section": _legal_bases_section(legal_bases_context),
        },
    )
    t0 = time.monotonic()
    out = await _llm_check_call(
        system=system, user_content=user_content, source_text=combined,
        case_id=case_id, playbook_revision=playbook_revision, label=check_instruction,
    )
    elapsed = round(time.monotonic() - t0, 2)
    logger.info(
        "run_check_rag completed: compliant=%s doc=%s chunks=%d confidence=%.2f elapsed=%.2fs  [request_id=%s]",
        out.is_compliant,
        document_id,
        len(chunks),
        out.confidence,
        elapsed,
        get_request_id(),
    )
    return out


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
    system = system + CHECK_OUTPUT_GUIDANCE
    user_tpl = await get_active_template("check_rag_cross_user")
    user_content = render(
        user_tpl or DEFAULT_CHECK_RAG_CROSS_USER,
        {
            "requirement": sanitize_prompt_field(check_instruction, max_chars=_CHECK_INSTRUCTION_MAX_CHARS),
            "excerpts": sanitize_prompt_field(combined, max_chars=cross_rag_limit),
            "legal_bases_section": _legal_bases_section(legal_bases_context),
        },
    )
    t0 = time.monotonic()
    out = await _llm_check_call(
        system=system, user_content=user_content, source_text=combined,
        case_id=case_id, playbook_revision=playbook_revision, label=check_instruction,
    )
    elapsed = round(time.monotonic() - t0, 2)
    logger.info(
        "run_cross_document_check_rag completed: compliant=%s case=%s chunks=%d confidence=%.2f elapsed=%.2fs  [request_id=%s]",
        out.is_compliant,
        case_id,
        len(chunks),
        out.confidence,
        elapsed,
        get_request_id(),
    )
    return out
