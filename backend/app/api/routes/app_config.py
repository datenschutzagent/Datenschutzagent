"""Public app configuration endpoint — no authentication required."""
from fastapi import APIRouter
from pydantic import BaseModel

from app.config import settings
from app.services.org_profile_loader import (
    get_org_name,
    get_processing_context_options,
)

router = APIRouter()


class ProcessingContextOption(BaseModel):
    value: str
    label: str


class AppConfigResponse(BaseModel):
    app_name: str
    org_name: str
    org_profile: str


@router.get("/config", response_model=AppConfigResponse, tags=["config"])
def get_app_config() -> AppConfigResponse:
    """
    Return public application configuration for the frontend.
    No authentication required (like /health and /auth/config).
    """
    return AppConfigResponse(
        app_name=settings.app_name,
        org_name=get_org_name(settings),
        org_profile=(settings.org_profile or "default").strip() or "default",
    )
