"""ORM models for Data Subject Requests (Art. 15–22 DSGVO)."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import Date, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models._db.base import Base


class DSRRequestModel(Base):
    """Betroffenenrechts-Anfragen (Art. 15–22 DSGVO)."""

    __tablename__ = "dsr_requests"
    __table_args__ = (
        Index("ix_dsr_requests_status", "status"),
        Index("ix_dsr_requests_response_deadline", "response_deadline"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    request_type: Mapped[str] = mapped_column(String(50), nullable=False)
    requestor_name: Mapped[str | None] = mapped_column(String(500), nullable=True)
    requestor_email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    department: Mapped[str | None] = mapped_column(String(200), nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="received")
    assignee: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    received_at: Mapped[date] = mapped_column(Date, nullable=False)
    response_deadline: Mapped[date] = mapped_column(Date, nullable=False)
    responded_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    response_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    draft_response: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_notified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    activity_logs: Mapped[list[DSRActivityLogModel]] = relationship(
        "DSRActivityLogModel", back_populates="request", cascade="all, delete-orphan"
    )


class DSRActivityLogModel(Base):
    """Aktivitätsprotokoll für DSR-Anfragen."""

    __tablename__ = "dsr_activity_log"
    __table_args__ = (Index("ix_dsr_activity_log_request_id", "request_id"),)

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    request_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("dsr_requests.id", ondelete="CASCADE"),
        nullable=False,
    )
    event_type: Mapped[str] = mapped_column(String(80), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )

    request: Mapped[DSRRequestModel] = relationship(
        "DSRRequestModel", back_populates="activity_logs"
    )
