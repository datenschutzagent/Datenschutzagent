"""ORM models for Technisch-Organisatorische Maßnahmen (Art. 32 DSGVO)."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models._db.base import Base


class TOMModel(Base):
    """Technisch-Organisatorische Maßnahmen (Art. 32 DSGVO)."""

    __tablename__ = "tom_measures"
    __table_args__ = (
        Index("ix_tom_measures_category", "category"),
        Index("ix_tom_measures_status", "implementation_status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    implementation_status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="planned"
    )
    responsible: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    review_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    evidence: Mapped[str | None] = mapped_column(Text, nullable=True)
    department_codes: Mapped[list[str] | None] = mapped_column(
        ARRAY(String), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )


class CaseMitigationLinkModel(Base):
    """Eine angewendete Mitigation (aus dem YAML-Katalog) für einen Case.

    Wird in der DSFA-Generierung herangezogen, um inherent → residual zu
    rechnen. Optional kann eine konkrete TOM (``tom_id``) und ein
    Nachweisdokument (``evidence_doc_id``) referenziert werden.
    """

    __tablename__ = "case_mitigation_links"
    __table_args__ = (
        UniqueConstraint(
            "case_id", "mitigation_id", name="uq_case_mitigation_links_case_mitigation"
        ),
        Index("ix_case_mitigation_links_case_id", "case_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    case_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("cases.id", ondelete="CASCADE"),
        nullable=False,
    )
    mitigation_id: Mapped[str] = mapped_column(String(80), nullable=False)
    tom_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tom_measures.id", ondelete="SET NULL"),
        nullable=True,
    )
    evidence_doc_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="SET NULL"),
        nullable=True,
    )
    applied_by: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    applied_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )


class TOMAttachmentModel(Base):
    """File attachments for TOM measures (evidence files)."""

    __tablename__ = "tom_attachments"
    __table_args__ = (Index("ix_tom_attachments_tom_id", "tom_id"),)

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tom_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tom_measures.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    format: Mapped[str] = mapped_column(String(20), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    storage_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    uploaded_by: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
