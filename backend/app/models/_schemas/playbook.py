"""Playbook-related schemas."""
from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class PlaybookCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    version: str = Field(..., min_length=1, max_length=50)
    content: dict[str, Any]
    case_type: str | None = Field(default=None, max_length=100)
    department: str | None = Field(default=None, max_length=200)


class PlaybookUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    version: str | None = Field(default=None, max_length=50)
    content: dict[str, Any] | None = None
    case_type: str | None = Field(default=None, max_length=100)
    department: str | None = Field(default=None, max_length=200)
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


class PlaybookRevisionResponse(BaseModel):
    id: UUID
    playbook_id: UUID
    version: str
    content: dict[str, Any]
    changed_by: str
    created_at: datetime

    model_config = {"from_attributes": True}


class PlaybookMatchResult(BaseModel):
    """Playbook plus match score from GET /playbooks/for-selection."""

    playbook: PlaybookResponse
    match_priority: int
