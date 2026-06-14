"""Global API audit log model – records every mutating API call (POST/PUT/PATCH/DELETE)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, Index, Integer, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models._db.base import Base


class APIAuditLogModel(Base):
    """Immutable record of a mutating HTTP request.

    user_id has no FK so the log survives user deletion (DSGVO retention).
    No request body or PII is stored – only endpoint, method, status, and identity.
    """

    __tablename__ = "api_audit_log"
    __table_args__ = (
        Index("ix_api_audit_log_user_id_timestamp", "user_id", "timestamp"),
        Index("ix_api_audit_log_request_id", "request_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True
    )
    endpoint: Mapped[str] = mapped_column(String(255), nullable=False)
    method: Mapped[str] = mapped_column(String(10), nullable=False)
    status_code: Mapped[int] = mapped_column(Integer, nullable=False)
    request_id: Mapped[str] = mapped_column(String(36), nullable=False, default="-")
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
