import uuid
from typing import List
from uuid import UUID

from pydantic import BaseModel, Field

from app.config import settings
from app.core.llm import create_agent
from app.models.schemas import FindingSeverityEnum

# Per-document character limit for LLM context (single-doc and cross-doc)
CONTEXT_CHARS_PER_DOC = 15000
# Max context size for RAG-assembled chunks (single document check)
RAG_CONTEXT_CHARS = 20000


class CheckResult(BaseModel):
    is_compliant: bool = Field(description="True if the check passed, False otherwise.")
    severity: FindingSeverityEnum = Field(description="Severity of the finding if not compliant.")
    description: str = Field(description="Explanation of the finding.")
    evidence: List[str] = Field(description="Quotes from the text supporting the finding.")
    recommendation: str = Field(description="Recommendation to fix the issue.")


async def run_check(document_text: str, check_instruction: str) -> CheckResult:
    """Run a single check against a document using the LLM."""
    agent = create_agent(
        system_prompt="You are a strict data protection auditor. Analyze the provided document text against the specific requirement."
    )
    truncated_text = document_text[:20000] if document_text else ""
    prompt = f"""
    Requirement: {check_instruction}

    Document Text:
    ---
    {truncated_text}
    ---

    Evaluate if the document meets the requirement.
    """
    result = await agent.run(prompt, result_type=CheckResult)
    return result.data


async def run_cross_document_check(
    documents: List[tuple[UUID, str]],
    check_instruction: str,
) -> CheckResult:
    """
    Run a single check across multiple documents (case-level / cross-document).
    documents: list of (document_id, extracted_text). Findings from this check
    are persisted with document_id=None.
    """
    agent = create_agent(
        system_prompt=(
            "You are a strict data protection auditor. Analyze the following set of documents "
            "as a whole (e.g. consistency between them, completeness across documents). "
            "Answer based on the combined context and the given requirement."
        )
    )
    parts: List[str] = []
    for i, (doc_id, text) in enumerate(documents, 1):
        truncated = (text or "")[:CONTEXT_CHARS_PER_DOC]
        parts.append(f"--- Document {i} (id: {doc_id}) ---\n{truncated}")
    combined = "\n\n".join(parts)
    prompt = f"""
    Requirement: {check_instruction}

    Documents (consider all of them together):
    {combined}

    Evaluate whether the set of documents meets the requirement (e.g. consistency, completeness).
    """
    result = await agent.run(prompt, result_type=CheckResult)
    return result.data


async def run_check_rag(document_id: UUID, case_id: UUID, check_instruction: str) -> CheckResult | None:
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
    agent = create_agent(
        system_prompt=(
            "You are a strict data protection auditor. You are given relevant excerpts from a document "
            "(retrieved by semantic search). Analyze these excerpts against the specific requirement."
        )
    )
    prompt = f"""
    Requirement: {check_instruction}

    Relevant document excerpts:
    ---
    {combined}
    ---

    Evaluate if the document (based on these excerpts) meets the requirement.
    """
    result = await agent.run(prompt, result_type=CheckResult)
    return result.data


async def run_cross_document_check_rag(case_id: UUID, check_instruction: str) -> CheckResult | None:
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
    agent = create_agent(
        system_prompt=(
            "You are a strict data protection auditor. You are given relevant excerpts from "
            "multiple documents (retrieved by semantic search). Analyze them as a whole against the requirement."
        )
    )
    prompt = f"""
    Requirement: {check_instruction}

    Relevant excerpts from case documents:
    ---
    {combined}
    ---

    Evaluate whether the set of documents (based on these excerpts) meets the requirement.
    """
    result = await agent.run(prompt, result_type=CheckResult)
    return result.data
