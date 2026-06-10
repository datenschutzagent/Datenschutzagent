"""DSGVO compliance ORM models: DSR, DataBreach, AVV, TOM, PrivacyPolicy, CaseTemplate."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models._db.base import Base

if TYPE_CHECKING:
    from app.models._db.case import CaseModel


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


class AVVContractModel(Base):
    """Auftragsverarbeitungsverträge (Art. 28 DSGVO)."""

    __tablename__ = "avv_contracts"
    __table_args__ = (
        Index("ix_avv_contracts_status", "status"),
        Index("ix_avv_contracts_partner_name", "partner_name"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    partner_name: Mapped[str] = mapped_column(String(500), nullable=False)
    partner_type: Mapped[str] = mapped_column(
        String(50), nullable=False, default="processor"
    )
    subject_matter: Mapped[str | None] = mapped_column(Text, nullable=True)
    department: Mapped[str | None] = mapped_column(String(200), nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending")
    contract_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    expiry_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    assignee: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    storage_path: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    document_name: Mapped[str | None] = mapped_column(String(500), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    check_result: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    # ``risk_score``/``risk_level`` always represent the *residual* values so
    # legacy callers keep working. Inherent (pre-mitigation) values are kept
    # alongside for the risk-delta endpoint.
    risk_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    risk_level: Mapped[str | None] = mapped_column(String(20), nullable=True)
    inherent_risk_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    inherent_risk_level: Mapped[str | None] = mapped_column(String(20), nullable=True)
    # Provenance of the last risk assessment: "llm" | "rules" | "hybrid".
    risk_source: Mapped[str | None] = mapped_column(String(20), nullable=True)
    # Self-reported LLM confidence on [0.0, 1.0]; null for legacy records.
    risk_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    risk_assessment: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    risk_assessed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
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


class AvvMitigationLinkModel(Base):
    """Eine angewendete Mitigation (aus dem YAML-Katalog) für einen AVV-Vertrag."""

    __tablename__ = "avv_mitigation_links"
    __table_args__ = (
        UniqueConstraint(
            "avv_contract_id",
            "mitigation_id",
            name="uq_avv_mitigation_links_contract_mitigation",
        ),
        Index("ix_avv_mitigation_links_contract_id", "avv_contract_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    avv_contract_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("avv_contracts.id", ondelete="CASCADE"),
        nullable=False,
    )
    mitigation_id: Mapped[str] = mapped_column(String(80), nullable=False)
    tom_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tom_measures.id", ondelete="SET NULL"),
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


class PrivacyPolicyModel(Base):
    """Vorgangsspezifische Datenschutzerklärungen (Art. 13/14 DSGVO).

    Jede Datenschutzerklärung gehört zu genau einem Case. Mehrere Versionen
    pro Case sind möglich (`version` zählt pro Case hoch).
    """

    __tablename__ = "privacy_policies"
    __table_args__ = (Index("ix_privacy_policies_case_id", "case_id"),)

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    case_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("cases.id", ondelete="CASCADE"),
        nullable=False,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    title: Mapped[str] = mapped_column(
        String(500), nullable=False, default="Datenschutzerklärung"
    )
    content_markdown: Mapped[str] = mapped_column(Text, nullable=False, default="")
    version_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    created_by: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )

    case: Mapped[CaseModel] = relationship(
        "CaseModel", back_populates="privacy_policies"
    )


class CaseTemplateModel(Base):
    """Vorgangs-Vorlagen für häufig wiederkehrende Verarbeitungstätigkeiten."""

    __tablename__ = "case_templates"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    case_type: Mapped[str] = mapped_column(String(100), nullable=False)
    department: Mapped[str | None] = mapped_column(String(200), nullable=True)
    language: Mapped[str] = mapped_column(String(20), nullable=False, default="de")
    processing_context: Mapped[str | None] = mapped_column(String(500), nullable=True)
    special_category_data: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    international_transfer: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    is_builtin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_by: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )
