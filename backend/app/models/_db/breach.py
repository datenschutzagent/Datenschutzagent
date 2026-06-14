"""ORM models for Data Breaches (Art. 33/34 DSGVO)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models._db.base import Base


class DataBreachModel(Base):
    """Datenschutzverletzungen (Art. 33/34 DSGVO) – 72-Stunden-Meldepflicht."""

    __tablename__ = "data_breaches"
    __table_args__ = (
        Index("ix_data_breaches_status", "status"),
        Index("ix_data_breaches_discovered_at", "discovered_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    discovered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    notification_deadline: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    breach_type: Mapped[str] = mapped_column(String(100), nullable=False)
    affected_data_categories: Mapped[list[str] | None] = mapped_column(
        ARRAY(String), nullable=True
    )
    affected_persons_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    department: Mapped[str | None] = mapped_column(String(200), nullable=True)
    assignee: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="discovered"
    )
    risk_level: Mapped[str | None] = mapped_column(String(20), nullable=True)
    authority_notified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    subjects_notified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    authority_reference: Mapped[str | None] = mapped_column(String(200), nullable=True)
    measures_taken: Mapped[str | None] = mapped_column(Text, nullable=True)
    draft_notification: Mapped[str | None] = mapped_column(Text, nullable=True)
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

    activity_logs: Mapped[list[DataBreachActivityLogModel]] = relationship(
        "DataBreachActivityLogModel",
        back_populates="breach",
        cascade="all, delete-orphan",
    )


class DataBreachActivityLogModel(Base):
    """Aktivitätsprotokoll für Datenpannen."""

    __tablename__ = "data_breach_activity_log"
    __table_args__ = (Index("ix_data_breach_activity_log_breach_id", "breach_id"),)

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    breach_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("data_breaches.id", ondelete="CASCADE"),
        nullable=False,
    )
    event_type: Mapped[str] = mapped_column(String(80), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )

    breach: Mapped[DataBreachModel] = relationship(
        "DataBreachModel", back_populates="activity_logs"
    )
