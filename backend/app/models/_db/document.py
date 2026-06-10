"""Document and document comment ORM models."""
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.constants import DocumentExtractionStatus
from app.models._db.base import Base


class DocumentModel(Base):
    __tablename__ = "documents"
    __table_args__ = (
        Index("ix_documents_case_id", "case_id"),
        Index("ix_documents_extraction_status", "extraction_status"),
        Index("ix_documents_case_id_extraction_status", "case_id", "extraction_status"),
        Index("ix_documents_case_id_type", "case_id", "type"),
    )

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    case_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("cases.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    type: Mapped[str] = mapped_column(String(50), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    format: Mapped[str] = mapped_column(String(20), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    uploaded_by: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    storage_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=True)
    extraction_method: Mapped[str | None] = mapped_column(String(20), nullable=True)
    extraction_status: Mapped[str] = mapped_column(String(20), nullable=False, default=DocumentExtractionStatus.PENDING)
    extraction_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Extraction quality signals (nullable; set on successful extraction). Used to flag weak
    # extractions (e.g. scans with little recovered text) for human review.
    extraction_char_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    extraction_page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    extraction_ocr_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    case: Mapped["CaseModel"] = relationship("CaseModel", back_populates="documents")


class DocumentCommentModel(Base):
    """User comments on a document (discussion / notes)."""
    __tablename__ = "document_comments"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    case_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("cases.id", ondelete="CASCADE"), nullable=False)
    author: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    user_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
