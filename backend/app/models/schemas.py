"""Pydantic schemas for API request/response. Aligned with frontend types."""
from datetime import date, datetime
from typing import Any, Generic, Literal, TypeVar
from uuid import UUID

from pydantic import BaseModel, Field

T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    """Generic paginated list response used across list endpoints."""

    items: list[T]
    total: int
    skip: int = 0
    limit: int = 100

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
ExtractionStatusEnum = Literal["pending", "processing", "done", "failed"]


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
    extraction_status: ExtractionStatusEnum | None = None
    extraction_error: str | None = None

    model_config = {"from_attributes": True}


class DocumentUpdate(BaseModel):
    """Partial update for document (e.g. extracted content for LLM/checks)."""
    content: str | None = None


class DocumentCommentCreate(BaseModel):
    text: str = Field(..., min_length=1)


class DocumentCommentResponse(BaseModel):
    id: UUID
    document_id: UUID
    case_id: UUID
    author: str
    user_id: UUID | None = None
    text: str
    created_at: datetime

    model_config = {"from_attributes": True}


# --- Finding ---
SourceStrategyEnum = Literal["full_text", "rag"]


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
    source_strategy: SourceStrategyEnum | None = None
    due_date: date | None = None

    model_config = {"from_attributes": True}


class FindingUpdate(BaseModel):
    status: FindingStatusEnum
    due_date: date | None = None


class FindingCommentCreate(BaseModel):
    text: str = Field(..., min_length=1)


class FindingCommentResponse(BaseModel):
    id: UUID
    finding_id: UUID
    case_id: UUID
    author: str
    user_id: UUID | None = None
    text: str
    created_at: datetime

    model_config = {"from_attributes": True}


class FindingBulkUpdate(BaseModel):
    finding_ids: list[UUID]
    status: FindingStatusEnum


class FindingListResponse(BaseModel):
    items: list[FindingResponse]
    total: int


class CaseListResponse(BaseModel):
    items: list["CaseResponse"]
    total: int


# --- Case ---
class CaseCreate(BaseModel):
    title: str = Field(..., min_length=1)
    department: str = Field(..., min_length=1)
    case_type: str = Field(..., min_length=1)
    language: CaseLanguageEnum = "de"
    created_by: str = Field(default="", min_length=0)
    assignee: str = Field(default="", min_length=0)
    processing_context: str | None = Field(default=None, max_length=500)
    special_category_data: bool = False
    international_transfer: bool = False
    deadline: date | None = None
    auto_run_checks: bool = False


class CaseUpdate(BaseModel):
    title: str | None = None
    department: str | None = None
    case_type: str | None = None
    status: CaseStatusEnum | None = None
    language: CaseLanguageEnum | None = None
    assignee: str | None = None
    playbook_version: str | None = None
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


class PlaybookMatchResult(BaseModel):
    """Playbook plus match score from GET /playbooks/for-selection."""

    playbook: PlaybookResponse
    match_priority: int


# --- Legal Base (Rechtsgrundlagen) ---
ApplicabilityEnum = Literal["always", "conditional"]


class LegalBaseCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    short_name: str | None = Field(default=None, max_length=100)
    content: str = Field(default="")
    applicability: ApplicabilityEnum = "always"
    department_codes: list[str] | None = None
    case_types: list[str] | None = None
    internal_only: bool = False


class LegalBaseUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=500)
    short_name: str | None = None
    content: str | None = None
    applicability: ApplicabilityEnum | None = None
    department_codes: list[str] | None = None
    case_types: list[str] | None = None
    internal_only: bool | None = None


class LegalBaseResponse(BaseModel):
    id: UUID
    title: str
    short_name: str | None = None
    content: str
    applicability: ApplicabilityEnum
    department_codes: list[str] = Field(default_factory=list)
    case_types: list[str] = Field(default_factory=list)
    internal_only: bool = False
    created_at: datetime
    updated_at: datetime

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


# --- VVT Overview (university-level) ---
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


# --- DSB Report ---
DSFAAssessmentEnum = Literal["required", "not_required", "unclear"]


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


class AnnotatedDocumentListItem(BaseModel):
    """One document that has findings and can be downloaded as annotated DOCX."""
    document_id: UUID
    document_name: str
    finding_count: int


# --- User / Me ---
UserThemeEnum = Literal["light", "dark", "system"]
UserUILanguageEnum = Literal["de", "en"]


class UserPreferences(BaseModel):
    """User UI preferences (theme, language, placeholder for notifications)."""
    theme: UserThemeEnum | None = None
    language: UserUILanguageEnum | None = None
    notifications: dict[str, Any] | None = None  # placeholder for later


UserRoleEnum = Literal["viewer", "editor", "admin"]


class UserResponse(BaseModel):
    id: UUID
    display_name: str
    email: str | None = None
    role: UserRoleEnum = "viewer"
    preferences: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class UserUpdate(BaseModel):
    display_name: str | None = None
    email: str | None = None
    preferences: UserPreferences | dict[str, Any] | None = None


# --- Admin: Prompt templates (versioned) ---
class PromptTemplateResponse(BaseModel):
    id: UUID
    key: str
    version: str
    content: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class PromptTemplateCreate(BaseModel):
    key: str = Field(..., min_length=1, max_length=100)
    version: str | None = Field(default=None, max_length=50)
    content: str = Field(..., min_length=1)
    set_active: bool = True


class PromptTemplateUpdate(BaseModel):
    is_active: bool | None = None


class PromptTemplateKeyMeta(BaseModel):
    key: str
    description: str
    placeholders: list[str]


# --- Activity / Audit Log ---
class ActivityResponse(BaseModel):
    """Single activity log entry for the timeline."""
    id: UUID
    case_id: UUID
    event_type: str
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime

    model_config = {"from_attributes": True}


# --- Risk Score (Verbesserung 3) ---
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


# --- Playbook Coverage Preview (Verbesserung 6) ---
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


# --- Case Similarity (Verbesserung 7) ---
class CaseSimilarityResult(BaseModel):
    case_id: UUID
    title: str
    department: str
    case_type: str
    status: str
    overlap_score: float  # 0.0 – 1.0
    shared_check_names: list[str] = []
    resolution_summary: dict[str, int] = Field(default_factory=dict)


# --- Case Clone ---
class CaseCloneRequest(BaseModel):
    new_title: str = Field(..., min_length=1, max_length=500)
    new_department: str | None = None
    adapt_with_llm: bool = False


class CaseCloneResponse(BaseModel):
    case: "CaseResponse"
    adaptations: dict[str, str] | None = None


# --- Findings Stats ---
class FindingTrendItem(BaseModel):
    month: str  # ISO format YYYY-MM
    critical: int = 0
    high: int = 0
    medium: int = 0
    low: int = 0
    info: int = 0


class FindingsByDepartment(BaseModel):
    department: str
    critical: int = 0
    high: int = 0
    medium: int = 0
    low: int = 0
    info: int = 0
    total: int = 0


class TopFailingCheck(BaseModel):
    check_name: str
    category: str
    count: int
    severity_breakdown: dict[str, int] = Field(default_factory=dict)


class FindingStatsResponse(BaseModel):
    by_severity: dict[str, int] = Field(default_factory=dict)
    by_category: dict[str, int] = Field(default_factory=dict)
    by_department: list[FindingsByDepartment] = []
    top_failing_checks: list[TopFailingCheck] = []
    trend: list[FindingTrendItem] = []


# --- DSFA (Art. 35 DSGVO) ---
class DSFARisk(BaseModel):
    description: str
    likelihood: Literal["low", "medium", "high"]
    severity: Literal["low", "medium", "high"]
    mitigation: str


class DSFAAssessmentPayload(BaseModel):
    necessity_assessment: str
    proportionality_assessment: str
    risks: list[DSFARisk] = []
    residual_risk: Literal["low", "medium", "high"]
    dpo_consultation_required: bool
    measures: list[str] = []


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


# --- Finding Chat ---
class FindingChatMessageResponse(BaseModel):
    id: UUID
    finding_id: UUID
    case_id: UUID
    role: str  # user | assistant
    content: str
    created_at: datetime

    model_config = {"from_attributes": True}


class FindingChatMessageCreate(BaseModel):
    content: str = Field(..., min_length=1)


# --- DSR (Betroffenenrechte Art. 15–22 DSGVO) ---
DSRRequestTypeEnum = Literal["access", "rectification", "erasure", "portability", "restriction", "objection"]
DSRStatusEnum = Literal["received", "in_progress", "response_sent", "closed", "denied"]


class DSRRequestCreate(BaseModel):
    request_type: DSRRequestTypeEnum
    requestor_name: str | None = Field(default=None, max_length=500)
    requestor_email: str | None = Field(default=None, max_length=320)
    description: str | None = None
    department: str | None = Field(default=None, max_length=200)
    assignee: str = Field(default="", max_length=200)
    received_at: date
    deadline_extension_days: int = Field(default=0, ge=0, le=60)


class DSRRequestUpdate(BaseModel):
    status: DSRStatusEnum | None = None
    assignee: str | None = Field(default=None, max_length=200)
    response_summary: str | None = None
    responded_at: date | None = None
    department: str | None = Field(default=None, max_length=200)


class DSRRequestResponse(BaseModel):
    id: UUID
    request_type: DSRRequestTypeEnum
    requestor_name: str | None = None
    requestor_email: str | None = None
    description: str | None = None
    department: str | None = None
    status: DSRStatusEnum
    assignee: str
    received_at: date
    response_deadline: date
    responded_at: date | None = None
    response_summary: str | None = None
    draft_response: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DSRActivityResponse(BaseModel):
    id: UUID
    request_id: UUID
    event_type: str
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime

    model_config = {"from_attributes": True}


class DSRListResponse(BaseModel):
    items: list[DSRRequestResponse]
    total: int


# --- Retention ---
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


# --- Notifications ---
class NotificationTestResponse(BaseModel):
    smtp_enabled: bool
    status: str
    detail: str | None = None


# --- Datenpannen-Management (Art. 33/34 DSGVO) ---
DataBreachTypeEnum = Literal["confidentiality", "integrity", "availability"]
DataBreachStatusEnum = Literal[
    "discovered", "assessed", "reported_to_authority", "reported_to_subjects",
    "closed", "no_notification_required"
]
RiskLevelEnum = Literal["low", "medium", "high", "critical"]


class DataBreachCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    description: str | None = None
    discovered_at: datetime
    breach_type: DataBreachTypeEnum
    affected_data_categories: list[str] | None = None
    affected_persons_count: int | None = Field(default=None, ge=0)
    department: str | None = Field(default=None, max_length=200)
    assignee: str = Field(default="", max_length=200)
    risk_level: RiskLevelEnum | None = None
    measures_taken: str | None = None


class DataBreachUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=500)
    description: str | None = None
    status: DataBreachStatusEnum | None = None
    breach_type: DataBreachTypeEnum | None = None
    affected_data_categories: list[str] | None = None
    affected_persons_count: int | None = Field(default=None, ge=0)
    department: str | None = Field(default=None, max_length=200)
    assignee: str | None = Field(default=None, max_length=200)
    risk_level: RiskLevelEnum | None = None
    authority_notified_at: datetime | None = None
    subjects_notified_at: datetime | None = None
    authority_reference: str | None = Field(default=None, max_length=200)
    measures_taken: str | None = None


class DataBreachResponse(BaseModel):
    id: UUID
    title: str
    description: str | None = None
    discovered_at: datetime
    notification_deadline: datetime
    breach_type: DataBreachTypeEnum
    affected_data_categories: list[str] = Field(default_factory=list)
    affected_persons_count: int | None = None
    department: str | None = None
    assignee: str
    status: DataBreachStatusEnum
    risk_level: RiskLevelEnum | None = None
    authority_notified_at: datetime | None = None
    subjects_notified_at: datetime | None = None
    authority_reference: str | None = None
    measures_taken: str | None = None
    draft_notification: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DataBreachListResponse(BaseModel):
    items: list[DataBreachResponse]
    total: int


class DataBreachActivityResponse(BaseModel):
    id: UUID
    breach_id: UUID
    event_type: str
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime

    model_config = {"from_attributes": True}


# --- AVV-Management (Art. 28 DSGVO) ---
AVVPartnerTypeEnum = Literal["processor", "sub_processor"]
AVVStatusEnum = Literal["pending", "under_review", "signed", "expired", "terminated"]


class AVVContractCreate(BaseModel):
    partner_name: str = Field(..., min_length=1, max_length=500)
    partner_type: AVVPartnerTypeEnum = "processor"
    subject_matter: str | None = None
    department: str | None = Field(default=None, max_length=200)
    assignee: str = Field(default="", max_length=200)
    contract_date: date | None = None
    expiry_date: date | None = None
    notes: str | None = None


class AVVContractUpdate(BaseModel):
    partner_name: str | None = Field(default=None, min_length=1, max_length=500)
    partner_type: AVVPartnerTypeEnum | None = None
    subject_matter: str | None = None
    department: str | None = Field(default=None, max_length=200)
    status: AVVStatusEnum | None = None
    assignee: str | None = Field(default=None, max_length=200)
    contract_date: date | None = None
    expiry_date: date | None = None
    notes: str | None = None


class AVVContractResponse(BaseModel):
    id: UUID
    partner_name: str
    partner_type: AVVPartnerTypeEnum
    subject_matter: str | None = None
    department: str | None = None
    status: AVVStatusEnum
    contract_date: date | None = None
    expiry_date: date | None = None
    assignee: str
    document_name: str | None = None
    notes: str | None = None
    check_result: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AVVListResponse(BaseModel):
    items: list[AVVContractResponse]
    total: int


# --- TOM-Katalog (Art. 32 DSGVO) ---
TOMCategoryEnum = Literal[
    "access_control", "encryption", "pseudonymization", "availability",
    "integrity", "confidentiality", "resilience", "testing", "incident_response", "other"
]
TOMStatusEnum = Literal["planned", "in_progress", "implemented", "not_applicable"]


class TOMCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    description: str | None = None
    category: TOMCategoryEnum
    implementation_status: TOMStatusEnum = "planned"
    responsible: str = Field(default="", max_length=200)
    review_date: date | None = None
    evidence: str | None = None
    department_codes: list[str] | None = None


class TOMUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=500)
    description: str | None = None
    category: TOMCategoryEnum | None = None
    implementation_status: TOMStatusEnum | None = None
    responsible: str | None = Field(default=None, max_length=200)
    review_date: date | None = None
    evidence: str | None = None
    department_codes: list[str] | None = None


class TOMResponse(BaseModel):
    id: UUID
    title: str
    description: str | None = None
    category: TOMCategoryEnum
    implementation_status: TOMStatusEnum
    responsible: str
    review_date: date | None = None
    evidence: str | None = None
    department_codes: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TOMListResponse(BaseModel):
    items: list[TOMResponse]
    total: int


class TOMStatsResponse(BaseModel):
    total: int
    by_status: dict[str, int] = Field(default_factory=dict)
    by_category: dict[str, int] = Field(default_factory=dict)
    implementation_rate: float = 0.0


# --- Vorgangs-Vorlagen ---
class CaseTemplateCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: str | None = None
    case_type: str = Field(..., min_length=1, max_length=100)
    department: str | None = Field(default=None, max_length=200)
    language: CaseLanguageEnum = "de"
    processing_context: str | None = Field(default=None, max_length=500)
    special_category_data: bool = False
    international_transfer: bool = False


class CaseTemplateResponse(BaseModel):
    id: UUID
    name: str
    description: str | None = None
    case_type: str
    department: str | None = None
    language: CaseLanguageEnum
    processing_context: str | None = None
    special_category_data: bool
    international_transfer: bool
    is_builtin: bool
    created_by: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CaseTemplateApplyRequest(BaseModel):
    template_id: UUID
    title: str = Field(..., min_length=1, max_length=500)
    assignee: str = Field(default="", max_length=200)
    deadline: date | None = None
