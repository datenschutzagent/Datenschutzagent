"""User ORM model."""
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.constants import UserRole
from app.models._db.base import Base


class UserModel(Base):
    """User profile and preferences (current user via OIDC token or CURRENT_USER_ID or default)."""
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    oidc_sub: Mapped[str | None] = mapped_column(String(500), nullable=True, unique=True)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False, default="Standardnutzer")
    email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    role: Mapped[str] = mapped_column(String(20), nullable=False, default=UserRole.VIEWER)
    preferences: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    # Master-Switch für E-Mail-Benachrichtigungen (Frist-, Datenpannen-, Findings-,
    # Maturity-Trends usw.). Bei false werden keine E-Mails an diesen Nutzer
    # gesendet. Default true, damit bestehende Nutzer weiterhin informiert werden.
    notifications_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))
