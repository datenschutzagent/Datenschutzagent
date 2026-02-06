import uuid
from typing import List
from uuid import UUID

from pydantic import BaseModel, Field

from app.core.llm import create_agent
from app.models.schemas import FindingSeverityEnum

# Per-document character limit for LLM context (single-doc and cross-doc)
CONTEXT_CHARS_PER_DOC = 15000


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
