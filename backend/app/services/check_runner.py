import uuid
from typing import List
from uuid import UUID

from pydantic import BaseModel, Field

from app.config import settings
from app.core.llm import create_agent
from app.models.schemas import FindingSeverityEnum
from app.services.prompt_template_service import get_active_template, render

# Per-document character limit for LLM context (single-doc and cross-doc)
CONTEXT_CHARS_PER_DOC = 15000
# Max context size for RAG-assembled chunks (single document check)
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


class CheckResult(BaseModel):
    is_compliant: bool = Field(description="True if the check passed, False otherwise.")
    severity: FindingSeverityEnum = Field(description="Severity of the finding if not compliant.")
    description: str = Field(description="Explanation of the finding.")
    evidence: List[str] = Field(description="Quotes from the text supporting the finding.")
    recommendation: str = Field(description="Recommendation to fix the issue.")


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
) -> CheckResult:
    """Run a single check against a document using the LLM."""
    language_hint = _language_hint(language) if language else ""
    system_tpl = await get_active_template("check_full_text_document_system")
    system = render(system_tpl or DEFAULT_CHECK_FULL_TEXT_DOCUMENT_SYSTEM, {"language_hint": language_hint})
    user_tpl = await get_active_template("check_full_text_document_user")
    truncated_text = document_text[:CONTEXT_CHARS_PER_DOC] if document_text else ""
    user_content = render(
        user_tpl or DEFAULT_CHECK_FULL_TEXT_DOCUMENT_USER,
        {
            "requirement": check_instruction,
            "document_text": truncated_text,
            "legal_bases_section": _legal_bases_section(legal_bases_context),
        },
    )
    agent = create_agent(system_prompt=system)
    result = await agent.run(user_content, result_type=CheckResult)
    return result.data


async def run_cross_document_check(
    documents: List[tuple[UUID, str]],
    check_instruction: str,
    language: str | None = None,
    legal_bases_context: str | None = None,
) -> CheckResult:
    """
    Run a single check across multiple documents (case-level / cross-document).
    documents: list of (document_id, extracted_text). Findings from this check
    are persisted with document_id=None.
    """
    language_hint = _language_hint(language) if language else ""
    system_tpl = await get_active_template("check_full_text_cross_system")
    system = render(system_tpl or DEFAULT_CHECK_FULL_TEXT_CROSS_SYSTEM, {"language_hint": language_hint})
    parts: List[str] = []
    for i, (doc_id, text) in enumerate(documents, 1):
        truncated = (text or "")[:CONTEXT_CHARS_PER_DOC]
        parts.append(f"--- Document {i} (id: {doc_id}) ---\n{truncated}")
    combined = "\n\n".join(parts)
    user_tpl = await get_active_template("check_full_text_cross_user")
    user_content = render(
        user_tpl or DEFAULT_CHECK_FULL_TEXT_CROSS_USER,
        {
            "requirement": check_instruction,
            "documents": combined,
            "legal_bases_section": _legal_bases_section(legal_bases_context),
        },
    )
    agent = create_agent(system_prompt=system)
    result = await agent.run(user_content, result_type=CheckResult)
    return result.data


async def run_check_rag(
    document_id: UUID,
    case_id: UUID,
    check_instruction: str,
    language: str | None = None,
    legal_bases_context: str | None = None,
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
    if len(combined) > RAG_CONTEXT_CHARS:
        combined = combined[:RAG_CONTEXT_CHARS] + "\n\n[... truncated ...]"
    language_hint = _language_hint(language) if language else ""
    system_tpl = await get_active_template("check_rag_document_system")
    system = render(system_tpl or DEFAULT_CHECK_RAG_DOCUMENT_SYSTEM, {"language_hint": language_hint})
    user_tpl = await get_active_template("check_rag_document_user")
    user_content = render(
        user_tpl or DEFAULT_CHECK_RAG_DOCUMENT_USER,
        {
            "requirement": check_instruction,
            "excerpts": combined,
            "legal_bases_section": _legal_bases_section(legal_bases_context),
        },
    )
    agent = create_agent(system_prompt=system)
    result = await agent.run(user_content, result_type=CheckResult)
    return result.data


async def run_cross_document_check_rag(
    case_id: UUID,
    check_instruction: str,
    language: str | None = None,
    legal_bases_context: str | None = None,
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
    if len(combined) > CONTEXT_CHARS_PER_DOC * 3:
        combined = combined[: CONTEXT_CHARS_PER_DOC * 3] + "\n\n[... truncated ...]"
    language_hint = _language_hint(language) if language else ""
    system_tpl = await get_active_template("check_rag_cross_system")
    system = render(system_tpl or DEFAULT_CHECK_RAG_CROSS_SYSTEM, {"language_hint": language_hint})
    user_tpl = await get_active_template("check_rag_cross_user")
    user_content = render(
        user_tpl or DEFAULT_CHECK_RAG_CROSS_USER,
        {
            "requirement": check_instruction,
            "excerpts": combined,
            "legal_bases_section": _legal_bases_section(legal_bases_context),
        },
    )
    agent = create_agent(system_prompt=system)
    result = await agent.run(user_content, result_type=CheckResult)
    return result.data
