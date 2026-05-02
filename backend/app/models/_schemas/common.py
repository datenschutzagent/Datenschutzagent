"""Shared type aliases, enums, and the generic PaginatedResponse."""
from typing import Any, Generic, Literal, TypeVar
from pydantic import BaseModel
from app.constants import (
    CaseStatus, CheckStrategy, DocumentExtractionMethod, DocumentExtractionStatus,
    FindingSeverity, FindingStatus,
)

T = TypeVar("T")

class PaginatedResponse(BaseModel, Generic[T]):
    """Generic paginated list response used across list endpoints."""
    items: list[T]
    total: int
    skip: int = 0
    limit: int = 100

CaseStatusEnum = Literal[
    CaseStatus.INTAKE, CaseStatus.IN_REVIEW, CaseStatus.QUESTIONS_PENDING,
    CaseStatus.REVISION, CaseStatus.READY_FOR_DECISION, CaseStatus.COMPLETED,
]
DocumentTypeEnum = Literal[
    "vvt", "screening", "info_sheet_de", "info_sheet_en", "dsfa", "avv", "other"
]
DocumentFormatEnum = Literal["docx", "pdf", "xlsx", "doc"]
FindingSeverityEnum = Literal[
    FindingSeverity.CRITICAL, FindingSeverity.HIGH, FindingSeverity.MEDIUM,
    FindingSeverity.LOW, FindingSeverity.INFO,
]
FindingStatusEnum = Literal[
    FindingStatus.OPEN, FindingStatus.ACCEPTED, FindingStatus.OVERRULED, FindingStatus.FIXED,
]
CaseLanguageEnum = Literal["de", "en", "de_en"]
ExtractionMethodEnum = Literal[DocumentExtractionMethod.TEXT, DocumentExtractionMethod.OCR]
ExtractionStatusEnum = Literal[
    DocumentExtractionStatus.PENDING, DocumentExtractionStatus.PROCESSING,
    DocumentExtractionStatus.DONE, DocumentExtractionStatus.FAILED,
]
SourceStrategyEnum = Literal[CheckStrategy.FULL_TEXT, CheckStrategy.RAG]
ApplicabilityEnum = Literal["always", "conditional"]
VVTFieldStatusEnum = Literal["filled", "missing", "inconsistent"]
DSFAAssessmentEnum = Literal["required", "not_required", "unclear"]
UserThemeEnum = Literal["light", "dark", "system"]
UserUILanguageEnum = Literal["de", "en"]
UserRoleEnum = Literal["viewer", "editor", "admin"]
DSRRequestTypeEnum = Literal["access", "rectification", "erasure", "portability", "restriction", "objection"]
DSRStatusEnum = Literal["received", "in_progress", "response_sent", "closed", "denied"]
DataBreachTypeEnum = Literal["confidentiality", "integrity", "availability"]
DataBreachStatusEnum = Literal[
    "discovered", "assessed", "reported_to_authority", "reported_to_subjects",
    "closed", "no_notification_required"
]
RiskLevelEnum = Literal["low", "medium", "high", "critical"]
AVVPartnerTypeEnum = Literal["processor", "sub_processor"]
AVVStatusEnum = Literal["pending", "under_review", "signed", "expired", "terminated"]
TOMCategoryEnum = Literal[
    "access_control", "encryption", "pseudonymization", "availability",
    "integrity", "confidentiality", "resilience", "testing", "incident_response", "other"
]
TOMStatusEnum = Literal["planned", "in_progress", "implemented", "not_applicable"]
