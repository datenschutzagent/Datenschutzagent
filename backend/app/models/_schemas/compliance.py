"""Compliance-related schemas: DSR, DataBreach, AVV, TOM, CaseTemplate."""

from datetime import date, datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from .common import (
    AVVPartnerTypeEnum,
    AVVStatusEnum,
    CaseLanguageEnum,
    DataBreachStatusEnum,
    DataBreachTypeEnum,
    DocumentFormatEnum,
    DSRRequestTypeEnum,
    DSRStatusEnum,
    RiskLevelEnum,
    TOMCategoryEnum,
    TOMStatusEnum,
)


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


class DSRMonthlyVolumeItem(BaseModel):
    month: str
    count: int


class DSRStatsResponse(BaseModel):
    total: int
    by_type: dict[str, int] = Field(default_factory=dict)
    by_status: dict[str, int] = Field(default_factory=dict)
    avg_response_days: float | None = None
    on_time_rate: float | None = None
    overdue_count: int = 0
    monthly_volume: list[DSRMonthlyVolumeItem] = []


class DataBreachMonthlyItem(BaseModel):
    month: str
    count: int
    total_persons: int


class DataBreachStatsResponse(BaseModel):
    total: int
    by_status: dict[str, int] = Field(default_factory=dict)
    by_risk_level: dict[str, int] = Field(default_factory=dict)
    by_breach_type: dict[str, int] = Field(default_factory=dict)
    notification_compliance_rate: float | None = None
    avg_affected_persons: float | None = None
    monthly_trend: list[DataBreachMonthlyItem] = []


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

    @field_validator("affected_data_categories", mode="before")
    @classmethod
    def coerce_none_to_list(cls, v: list[str] | None) -> list[str]:
        return v or []


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


class AVVStatsResponse(BaseModel):
    total: int
    by_status: dict[str, int] = Field(default_factory=dict)
    expiring_soon: int = 0
    expired: int = 0
    avg_risk_score: float | None = None
    by_risk_level: dict[str, int] = Field(default_factory=dict)


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
    risk_score: int | None = None
    risk_level: RiskLevelEnum | None = None
    inherent_risk_score: int | None = None
    inherent_risk_level: RiskLevelEnum | None = None
    risk_source: str | None = None
    risk_confidence: float | None = None
    risk_assessed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AVVListResponse(BaseModel):
    items: list[AVVContractResponse]
    total: int


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

    @field_validator("department_codes", mode="before")
    @classmethod
    def coerce_none_to_list(cls, v: list[str] | None) -> list[str]:
        return v or []


class TOMListResponse(BaseModel):
    items: list[TOMResponse]
    total: int


class TOMStatsResponse(BaseModel):
    total: int
    by_status: dict[str, int] = Field(default_factory=dict)
    by_category: dict[str, int] = Field(default_factory=dict)
    implementation_rate: float = 0.0


class TOMAttachmentResponse(BaseModel):
    id: UUID
    tom_id: UUID
    name: str
    format: DocumentFormatEnum
    size_bytes: int
    uploaded_by: str
    uploaded_at: datetime

    model_config = {"from_attributes": True}


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


# ---------------------------------------------------------------------------
# Mitigation catalog: linking + delta
# ---------------------------------------------------------------------------


class MitigationReductionResponse(BaseModel):
    score_delta: float = 0.0
    dimension_deltas: dict[str, float] = Field(default_factory=dict)
    likelihood_delta: int = 0
    severity_delta: int = 0
    applicable_risk_keywords: list[str] = Field(default_factory=list)


class MitigationCatalogEntry(BaseModel):
    id: str
    label: str
    description: str = ""
    applies_to: str
    tom_category: str | None = None
    evidence_required: bool = False
    reduction: MitigationReductionResponse


class MitigationCatalogResponse(BaseModel):
    enabled: bool
    min_likelihood: int
    min_severity: int
    min_avv_score: float
    catalog: list[MitigationCatalogEntry]


class MitigationLinkRequest(BaseModel):
    """Body for POST /cases/{id}/mitigations or /avv/{id}/mitigations."""

    mitigation_id: str = Field(..., min_length=1, max_length=80)
    tom_id: UUID | None = None
    evidence_doc_id: UUID | None = None
    notes: str | None = None


class CaseMitigationLinkResponse(BaseModel):
    id: UUID
    case_id: UUID
    mitigation_id: str
    tom_id: UUID | None = None
    evidence_doc_id: UUID | None = None
    applied_by: str
    notes: str | None = None
    applied_at: datetime
    catalog_entry: MitigationCatalogEntry | None = None

    model_config = {"from_attributes": True}


class AvvMitigationLinkResponse(BaseModel):
    id: UUID
    avv_contract_id: UUID
    mitigation_id: str
    tom_id: UUID | None = None
    applied_by: str
    notes: str | None = None
    applied_at: datetime
    catalog_entry: MitigationCatalogEntry | None = None

    model_config = {"from_attributes": True}


class RiskDeltaSide(BaseModel):
    """One snapshot (inherent or residual) of a risk-bearing object."""

    risk_score: int | None = None
    risk_level: str | None = None


class RiskDeltaResponse(BaseModel):
    """Before/after view returned by /cases/{id}/risk-delta and /avv/{id}/risk-delta."""

    target_type: str  # 'avv' | 'dsfa'
    target_id: UUID
    inherent: RiskDeltaSide
    residual: RiskDeltaSide
    applied_mitigations: list[str] = Field(default_factory=list)
    applied_effects: list[dict[str, Any]] = Field(default_factory=list)
    assessed_at: datetime | None = None
