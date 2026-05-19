"""DSB report and DSFA schemas."""
from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field

from .common import DSFAAssessmentEnum


class DSBReportSummary(BaseModel):
    """Summary section of the DSB report."""
    total_documents: int = 0
    total_findings: int = 0
    critical_findings: int = 0
    high_findings: int = 0
    dsfa_required: bool = False
    dsfa_assessment: DSFAAssessmentEnum = "unclear"
    vvt_completeness: int = 0
    vvt_available: bool = False


class DSBReportRisk(BaseModel):
    """Single risk entry (from finding) in the DSB report."""
    title: str
    severity: Literal["critical", "high", "medium", "low", "info"]
    description: str


class DSBReportResponse(BaseModel):
    """Full DSB summary report for a case."""
    case_id: UUID
    case_title: str
    generated_at: datetime
    playbook_version: str = ""
    status: str
    summary: DSBReportSummary
    risks: list[DSBReportRisk] = []
    open_questions: list[str] = []
    recommendations: list[str] = []
    next_steps: list[str] = []
    next_steps_is_suggested: bool = True


class DSFARisk(BaseModel):
    description: str
    likelihood: Literal["low", "medium", "high"]
    severity: Literal["low", "medium", "high"]
    mitigation: str
    # Numerische Skala (1-5) und resultierendes Risiko-Level aus der
    # ISO-27005-Matrix. Optional für Backward-Compatibility mit Legacy-Records,
    # die noch keine numerischen Felder haben.
    likelihood_score: int | None = None
    severity_score: int | None = None
    risk_level: Literal["low", "medium", "high", "critical"] | None = None


class DSFAAssessmentPayload(BaseModel):
    necessity_assessment: str
    proportionality_assessment: str
    risks: list[DSFARisk] = []
    residual_risk: Literal["low", "medium", "high", "critical"]
    dpo_consultation_required: bool
    measures: list[str] = []
    # Methodik-Metadaten (Phase B2).
    confidence: float | None = None
    low_confidence: bool | None = None
    scale_version: str | None = None


class DSFAResponse(BaseModel):
    case_id: UUID
    status: str  # draft | finalized
    payload: dict[str, Any]
    generated_at: datetime
    finalized_at: datetime | None = None
    finalized_by: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DSFAJobStatusResponse(BaseModel):
    job_id: UUID
    case_id: UUID
    status: str
    error: str | None = None
    created_at: datetime
    updated_at: datetime


class DSFAFinalizeRequest(BaseModel):
    finalized_by: str = Field(..., min_length=1)
