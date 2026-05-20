"""Admin and user-related schemas."""
from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from .common import UserRoleEnum, UserThemeEnum, UserUILanguageEnum


class UserPreferences(BaseModel):
    """User UI preferences (theme, language, placeholder for notifications)."""
    theme: UserThemeEnum | None = None
    language: UserUILanguageEnum | None = None
    notifications: dict[str, Any] | None = None  # placeholder for later


class UserResponse(BaseModel):
    id: UUID
    display_name: str
    email: str | None = None
    role: UserRoleEnum = "viewer"
    preferences: dict[str, Any] = Field(default_factory=dict)
    notifications_enabled: bool = True
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class UserUpdate(BaseModel):
    display_name: str | None = None
    email: str | None = None
    preferences: UserPreferences | dict[str, Any] | None = None
    notifications_enabled: bool | None = None


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


class NotificationTestResponse(BaseModel):
    smtp_enabled: bool
    status: str
    detail: str | None = None
