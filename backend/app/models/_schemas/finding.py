"""Finding-related schemas."""

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, Field

from .common import FindingSeverityEnum, FindingStatusEnum, SourceStrategyEnum


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
    case_title: str | None = None  # eagerly loaded when available
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


class FindingBulkDelete(BaseModel):
    finding_ids: list[UUID]


class FindingListResponse(BaseModel):
    items: list[FindingResponse]
    total: int


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


class ResolutionVelocityItem(BaseModel):
    severity: str
    avg_days_to_fix: float
    sample_size: int


class FindingStatsResponse(BaseModel):
    by_severity: dict[str, int] = Field(default_factory=dict)
    by_category: dict[str, int] = Field(default_factory=dict)
    by_department: list[FindingsByDepartment] = []
    top_failing_checks: list[TopFailingCheck] = []
    trend: list[FindingTrendItem] = []
    resolution_velocity: list[ResolutionVelocityItem] = []


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
