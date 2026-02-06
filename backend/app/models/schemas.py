"""Pydantic schemas for API request/response. Aligned with frontend types."""
from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field

CaseStatusEnum = Literal[
    "intake", "in_review", "questions_pending", "revision", "ready_for_decision", "completed"
]
DocumentTypeEnum = Literal[
    "vvt", "screening", "info_sheet_de", "info_sheet_en", "dsfa", "avv", "other"
]
DocumentFormatEnum = Literal["docx", "pdf", "xlsx", "doc"]
FindingSeverityEnum = Literal["critical", "high", "medium", "low", "info"]
FindingStatusEnum = Literal["open", "accepted", "overruled", "fixed"]
CaseLanguageEnum = Literal["de", "en", "de_en"]


# --- Document ---
ExtractionMethodEnum = Literal["text", "ocr"]


class DocumentResponse(BaseModel):
    id: UUID
    name: str
    type: DocumentTypeEnum
    version: int
    uploaded_at: datetime
    uploaded_by: str
    size_bytes: int
    format: DocumentFormatEnum
    case_id: UUID
    extraction_method: ExtractionMethodEnum | None = None

    model_config = {"from_attributes": True}


# --- Finding ---
class FindingResponse(BaseModel):
    id: UUID
    check_name: str
    severity: FindingSeverityEnum
    status: FindingStatusEnum
    category: str
    description: str
    evidence: list[str]
    recommendation: str
    document_id: UUID | None = None
    case_id: UUID

    model_config = {"from_attributes": True}


class FindingUpdate(BaseModel):
    status: FindingStatusEnum


# --- Case ---
class CaseCreate(BaseModel):
    title: str = Field(..., min_length=1)
    department: str = Field(..., min_length=1)
    case_type: str = Field(..., min_length=1)
    language: CaseLanguageEnum = "de"
    created_by: str = Field(default="", min_length=0)
    assignee: str = Field(default="", min_length=0)


class CaseUpdate(BaseModel):
    title: str | None = None
    department: str | None = None
    case_type: str | None = None
    status: CaseStatusEnum | None = None
    language: CaseLanguageEnum | None = None
    assignee: str | None = None
    playbook_version: str | None = None


class RunChecksRequest(BaseModel):
    playbook_id: UUID = Field(..., description="Playbook whose checks to run against case documents.")


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
    documents: list[DocumentResponse] = []
    findings: list[FindingResponse] = []

    model_config = {"from_attributes": True}


# --- Playbook ---
class PlaybookCreate(BaseModel):
    name: str = Field(..., min_length=1)
    version: str = Field(..., min_length=1)
    content: dict[str, Any]
    case_type: str | None = None
    department: str | None = None


class PlaybookUpdate(BaseModel):
    name: str | None = None
    version: str | None = None
    content: dict[str, Any] | None = None
    case_type: str | None = None
    department: str | None = None
    is_active: bool | None = None


class PlaybookResponse(BaseModel):
    id: UUID
    name: str
    version: str
    content: dict[str, Any]
    case_type: str | None
    department: str | None
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# --- VVT Normalization (canonical model) ---
VVTFieldStatusEnum = Literal["filled", "missing", "inconsistent"]


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


# --- DSB Report ---
class DSBReportSummary(BaseModel):
    """Summary section of the DSB report."""
    total_documents: int = 0
    total_findings: int = 0
    critical_findings: int = 0
    high_findings: int = 0
    dsfa_required: bool = False
    vvt_completeness: int = 0


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


class AnnotatedDocumentListItem(BaseModel):
    """One document that has findings and can be downloaded as annotated DOCX."""
    document_id: UUID
    document_name: str
    finding_count: int


# --- Activity / Audit Log ---
class ActivityResponse(BaseModel):
    """Single activity log entry for the timeline."""
    id: UUID
    case_id: UUID
    event_type: str
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime

    model_config = {"from_attributes": True}
