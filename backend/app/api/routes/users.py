"""Current user (me) API: profile and preferences."""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.database import get_db
from app.models.db import UserModel, orm_to_user_response
from app.models.schemas import UserResponse, UserUpdate

router = APIRouter()


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: UserModel = Depends(get_current_user)):
    """Return the current user (from OIDC token or CURRENT_USER_ID/default when OIDC disabled)."""
    return UserResponse(**orm_to_user_response(current_user))


@router.patch("/me", response_model=UserResponse)
async def update_me(
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
    return UserResponse(**orm_to_user_response(current_user))
