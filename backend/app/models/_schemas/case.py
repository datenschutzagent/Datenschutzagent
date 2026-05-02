"""Case-related schemas."""
from datetime import date, datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from .common import (
    CaseStatusEnum,
    CaseLanguageEnum,
    VVTFieldStatusEnum,
)
from .document import DocumentResponse
from .finding import FindingResponse


class CaseCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    department: str = Field(..., min_length=1, max_length=200)
    case_type: str = Field(..., min_length=1, max_length=100)
    language: CaseLanguageEnum = "de"
    created_by: str = Field(default="", max_length=200)
    assignee: str = Field(default="", max_length=200)
    processing_context: str | None = Field(default=None, max_length=500)
    special_category_data: bool = False
    international_transfer: bool = False
    deadline: date | None = None
    auto_run_checks: bool = False


class CaseUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=500)
    department: str | None = Field(default=None, max_length=200)
    case_type: str | None = Field(default=None, max_length=100)
    status: CaseStatusEnum | None = None
    language: CaseLanguageEnum | None = None
    assignee: str | None = Field(default=None, max_length=200)
    playbook_version: str | None = Field(default=None, max_length=50)
    processing_context: str | None = Field(default=None, max_length=500)
    special_category_data: bool | None = None
    international_transfer: bool | None = None
    deadline: date | None = None
    auto_run_checks: bool | None = None


class RunChecksRequest(BaseModel):
    playbook_id: UUID = Field(..., description="Playbook whose checks to run against case documents.")
    strategies: list[Literal["full_text", "rag"]] = Field(
        default=["full_text"],
        description="Run full_text and/or rag (RAG uses Weaviate chunks). Both can run in parallel for comparison.",
    )
    skip_resolved: bool = Field(
        default=True,
        description=(
            "When True (default), findings already resolved (accepted, fixed, overruled, in_review) "
            "are not re-created even if the check would fail again. "
            "Set to False to force a full re-check that ignores all prior review decisions."
        ),
    )


class CaseResponse(BaseModel):
    id: UUID
    title: str
    department: str
    case_type: str
    status: CaseStatusEnum
    language: CaseLanguageEnum
    created_at: datetime
    updated_at: datetime
    created_by: str
    assignee: str
    playbook_version: str
    processing_context: str | None = None
    special_category_data: bool = False
    international_transfer: bool = False
    deadline: date | None = None
    auto_run_checks: bool = False
    archived_at: datetime | None = None
    retention_months: int | None = None
    documents: list[DocumentResponse] = []
    findings: list[FindingResponse] = []

    model_config = {"from_attributes": True}

    @model_validator(mode="after")
    def sort_documents(self) -> "CaseResponse":
        """Sort documents by type then version, matching the previous orm_to_case_response behaviour."""
        self.documents = sorted(self.documents, key=lambda d: (d.type, d.version))
        return self


class CaseListResponse(BaseModel):
    items: list[CaseResponse]
    total: int


class ActivityResponse(BaseModel):
    """Single activity log entry for the timeline."""
    id: UUID
    case_id: UUID
    event_type: str
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime

    model_config = {"from_attributes": True}


class CaseRiskScoreHistoryItem(BaseModel):
    job_id: UUID
    created_at: datetime
    score: int
    findings_count: int
    critical: int
    high: int
    medium: int


class CaseRiskScoreResponse(BaseModel):
    """Current risk score and history for a case (derived from run_checks_jobs)."""
    case_id: UUID
    score: int  # 0-100, lower = better
    history: list[CaseRiskScoreHistoryItem] = []


class PlaybookCoverageItem(BaseModel):
    name: str
    category: str
    scope: str  # "document" | "case"
    applicable: bool
    reason: str


class PlaybookCoverageResponse(BaseModel):
    playbook_id: UUID
    case_id: UUID
    total_checks: int
    applicable_count: int
    checks: list[PlaybookCoverageItem] = []
    missing_document_types: list[str] = []


class CaseSimilarityResult(BaseModel):
    case_id: UUID
    title: str
    department: str
    case_type: str
    status: str
    overlap_score: float  # 0.0 – 1.0
    shared_check_names: list[str] = []
    resolution_summary: dict[str, int] = Field(default_factory=dict)


class CaseCloneRequest(BaseModel):
    new_title: str = Field(..., min_length=1, max_length=500)
    new_department: str | None = None
    adapt_with_llm: bool = False


class CaseCloneResponse(BaseModel):
    case: CaseResponse
    adaptations: dict[str, str] | None = None


class VVTFieldResponse(BaseModel):
    """Single field in the canonical VVT model."""
    field_name: str
    required: bool = True
    status: VVTFieldStatusEnum
    source_template: str = ""
    canonical_value: str | None = None
    evidence: str | None = None
    finding: str | None = None


class VVTNormalizationResponse(BaseModel):
    """Response for VVT normalization: template detection + extracted fields."""
    document_id: UUID | None = None
    document_name: str = ""
    source_template: str = ""
    fields: list[VVTFieldResponse] = []


class VVTOverviewItem(BaseModel):
    """One row in the VVT overview: case with VVT metadata (no LLM)."""
    case_id: UUID
    title: str
    department: str
    case_type: str
    status: str
    updated_at: datetime
    has_vvt_document: bool
    vvt_completeness: int | None = None  # from last DSB report if available
    vvt_document_name: str | None = None


class VVTOverviewStatsGroup(BaseModel):
    """Aggregation for one department or case_type."""
    name: str  # department or case_type value
    total_cases: int
    with_vvt: int
    without_vvt: int
    avg_completeness: float | None = None  # only over cases with report + VVT


class VVTOverviewStatsResponse(BaseModel):
    """Stats for VVT overview: totals + by department + by case_type."""
    total_cases: int = 0
    with_vvt: int = 0
    without_vvt: int = 0
    avg_completeness: float | None = None
    by_department: list[VVTOverviewStatsGroup] = []
    by_case_type: list[VVTOverviewStatsGroup] = []


class AnnotatedDocumentListItem(BaseModel):
    """One document that has findings and can be downloaded as annotated DOCX."""
    document_id: UUID
    document_name: str
    finding_count: int


class RetentionPreviewItem(BaseModel):
    case_id: UUID
    title: str
    department: str
    retention_months: int
    updated_at: datetime | None = None


class RetentionScanResponse(BaseModel):
    archived_count: int
    archived: list[RetentionPreviewItem] = []


class RetentionPreviewResponse(BaseModel):
    would_archive_count: int
    items: list[RetentionPreviewItem] = []
