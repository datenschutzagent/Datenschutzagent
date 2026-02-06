"""Pydantic schemas for API request/response. Aligned with frontend types."""
from datetime import datetime
from typing import Literal
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
