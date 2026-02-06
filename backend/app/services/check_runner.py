import uuid
from typing import List

from pydantic import BaseModel, Field

from app.core.llm import create_agent
from app.models.schemas import FindingSeverityEnum

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
    
    # Simple truncation to avoid context limits for MVP
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
