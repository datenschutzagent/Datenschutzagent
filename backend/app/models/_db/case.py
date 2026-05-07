"""Case and activity log ORM models."""
import uuid
from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.constants import CaseStatus
from app.models._db.base import Base


class CaseModel(Base):
    __tablename__ = "cases"
    __table_args__ = (
        Index("ix_cases_status", "status"),
        Index("ix_cases_department", "department"),
        Index("ix_cases_updated_at", "updated_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    department: Mapped[str] = mapped_column(String(200), nullable=False)
    case_type: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default=CaseStatus.INTAKE)
    language: Mapped[str] = mapped_column(String(20), nullable=False, default="de")
    created_by: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    assignee: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    playbook_version: Mapped[str] = mapped_column(String(50), nullable=False, default="")
    processing_context: Mapped[str | None] = mapped_column(String(500), nullable=True)
    special_category_data: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    international_transfer: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    deadline: Mapped[date | None] = mapped_column(Date, nullable=True)
    auto_run_checks: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, default=None)
    retention_months: Mapped[int | None] = mapped_column(Integer, nullable=True, default=None)
    recheck_interval_days: Mapped[int | None] = mapped_column(Integer, nullable=True, default=None)
    last_rechecked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, default=None)
    last_notified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, default=None)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    documents: Mapped[list["DocumentModel"]] = relationship("DocumentModel", back_populates="case", cascade="all, delete-orphan")
    findings: Mapped[list["FindingModel"]] = relationship("FindingModel", back_populates="case", cascade="all, delete-orphan")
    privacy_policies: Mapped[list["PrivacyPolicyModel"]] = relationship(
        "PrivacyPolicyModel",
        back_populates="case",
        cascade="all, delete-orphan",
        order_by="desc(PrivacyPolicyModel.version)",
    )


class ActivityLogModel(Base):
    """Audit log for case-related events (run_checks, finding_status_updated, etc.)."""
    __tablename__ = "activity_log"
    __table_args__ = (Index("ix_activity_log_case_id_created_at", "case_id", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    case_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("cases.id", ondelete="CASCADE"), nullable=False)
    event_type: Mapped[str] = mapped_column(String(80), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
