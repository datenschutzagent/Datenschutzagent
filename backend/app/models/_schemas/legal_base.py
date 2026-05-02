"""Legal base (Rechtsgrundlagen) schemas."""
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from .common import ApplicabilityEnum


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

    @field_validator("department_codes", "case_types", mode="before")
    @classmethod
    def coerce_none_to_list(cls, v: list[str] | None) -> list[str]:
        return v or []
