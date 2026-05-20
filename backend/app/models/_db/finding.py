"""Finding, finding comment, and chat message ORM models."""
import uuid
from datetime import UTC, date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.constants import FindingStatus
from app.models._db.base import Base


class FindingModel(Base):
    __tablename__ = "findings"
    __table_args__ = (
        Index("ix_findings_case_id", "case_id"),
        Index("ix_findings_case_id_status", "case_id", "status"),
        Index("ix_findings_case_id_severity", "case_id", "severity"),
        Index("ix_findings_document_id", "document_id"),
        # Supports the 6-month trend query in /findings/stats (WHERE created_at >= NOW() - INTERVAL '6 months')
        Index("ix_findings_created_at", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    case_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("cases.id", ondelete="CASCADE"), nullable=False)
    document_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("documents.id", ondelete="SET NULL"), nullable=True)
    check_name: Mapped[str] = mapped_column(String(300), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=FindingStatus.OPEN)
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    evidence: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, default=list)
    recommendation: Mapped[str] = mapped_column(Text, nullable=False, default="")
    source_strategy: Mapped[str | None] = mapped_column(String(20), nullable=True)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    # Cooldown-Marker für CRITICAL-Finding-Benachrichtigungen (Item 15).
    # Wird bei jeder gesendeten E-Mail aktualisiert, vergleichbar mit
    # CaseModel.last_notified_at.
    last_notified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))

    case: Mapped["CaseModel"] = relationship("CaseModel", back_populates="findings")

    @property
    def case_title(self) -> str | None:
        """Return the title of the related case when eagerly loaded; None otherwise."""
        try:
            if self.case is not None:
                return self.case.title
        except Exception:  # noqa: BLE001 – lazy-load guard (async context)
            pass
        return None


class FindingCommentModel(Base):
    """User comments on a finding (discussion / audit trail for status decisions)."""
    __tablename__ = "finding_comments"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    finding_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("findings.id", ondelete="CASCADE"), nullable=False)
    case_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("cases.id", ondelete="CASCADE"), nullable=False)
    author: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    user_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))


class FindingChatMessageModel(Base):
    """LLM chat messages per finding (finding remediation assistant)."""
    __tablename__ = "finding_chat_messages"
    __table_args__ = (Index("ix_finding_chat_messages_finding_id", "finding_id"),)

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    finding_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("findings.id", ondelete="CASCADE"), nullable=False)
    case_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("cases.id", ondelete="CASCADE"), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
