"""Current user (me) API: profile and preferences."""
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.db import UserModel, orm_to_user_response
from app.models.schemas import UserResponse, UserUpdate

router = APIRouter()

# Fixed default user ID when CURRENT_USER_ID is not set (must match main.py lifespan)
DEFAULT_USER_ID = uuid.UUID("00000000-0000-4000-8000-000000000001")


def _current_user_id() -> uuid.UUID:
    """Resolve current user ID from env or default."""
    raw = settings.current_user_id
    if raw and str(raw).strip():
        try:
            return uuid.UUID(str(raw).strip())
        except ValueError:
            pass
    return DEFAULT_USER_ID


@router.get("/me", response_model=UserResponse)
async def get_me(db: AsyncSession = Depends(get_db)):
    """Return the current user (from CURRENT_USER_ID or default user)."""
    user_id = _current_user_id()
    result = await db.execute(select(UserModel).where(UserModel.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return UserResponse(**orm_to_user_response(user))


@router.patch("/me", response_model=UserResponse)
async def update_me(
    body: UserUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update current user profile (display_name, preferences)."""
    user_id = _current_user_id()
    result = await db.execute(select(UserModel).where(UserModel.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if body.display_name is not None:
        user.display_name = body.display_name
    if body.email is not None:
        user.email = body.email
    if body.preferences is not None:
        prefs = body.preferences.model_dump(exclude_none=True) if hasattr(body.preferences, "model_dump") else body.preferences
        existing = dict(user.preferences or {})
        existing.update(prefs)
        user.preferences = existing
    await db.flush()
    await db.refresh(user)
    return UserResponse(**orm_to_user_response(user))
