"""Public app configuration endpoint — no authentication required."""

from fastapi import APIRouter, Request
from pydantic import BaseModel

from app.config import settings
from app.core.rate_limit import limiter
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
    processing_context_options: list[ProcessingContextOption]


@router.get("/config", response_model=AppConfigResponse, tags=["config"])
@limiter.limit("60/minute")
def get_app_config(request: Request) -> AppConfigResponse:
    """
    Return public application configuration for the frontend.
    No authentication required (like /health and /auth/config).
    """
    raw_options = get_processing_context_options(settings)
    return AppConfigResponse(
        app_name=settings.app_name,
        org_name=get_org_name(settings),
        org_profile=(settings.org_profile or "default").strip() or "default",
        processing_context_options=[
            ProcessingContextOption(value=o["value"], label=o["label"])
            for o in raw_options
        ],
    )
