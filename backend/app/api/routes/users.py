"""Current user (me) API: profile and preferences."""
import logging

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.core.rate_limit import limiter
from app.database import get_db
from app.models.db import UserModel
from app.models.schemas import UserResponse, UserUpdate

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: UserModel = Depends(get_current_user)):
    """Return the current user (from OIDC token or CURRENT_USER_ID/default when OIDC disabled)."""
    return UserResponse.model_validate(current_user)


@router.patch("/me", response_model=UserResponse)
@limiter.limit("30/minute")
async def update_me(
    request: Request,
    body: UserUpdate,
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update current user profile (display_name, preferences)."""
    if body.display_name is not None:
        current_user.display_name = body.display_name
    if body.email is not None:
        current_user.email = body.email
    if body.preferences is not None:
        prefs = body.preferences.model_dump(exclude_none=True) if hasattr(body.preferences, "model_dump") else body.preferences
        existing = dict(current_user.preferences or {})
        existing.update(prefs)
        current_user.preferences = existing
    await db.flush()
    await db.refresh(current_user)
    logger.info("User profile updated", extra={"user_id": str(current_user.id), "fields": list(body.model_fields_set)})
    return UserResponse.model_validate(current_user)
