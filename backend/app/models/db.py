"""SQLAlchemy ORM models."""
import uuid
from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from app.constants import (
    CaseStatus,
    DocumentExtractionStatus,
    FindingStatus,
    UserRole,
    WebhookDeliveryStatus,
)


class Base(DeclarativeBase):
    """Declarative base for all models."""
    type_annotation_map = {
        uuid.UUID: PG_UUID(as_uuid=True),
    }


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
    recheck_interval_days: Mapped[int | None] = mapped_column(Integer, nullable=True, default=None)  # Automatischer Re-Check alle X Tage
    last_rechecked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, default=None)
    last_notified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, default=None)  # Letzter Benachrichtigungsversand (Anti-Spam)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, default=None)  # Zeitpunkt des Abschlusses (Basis für Aufbewahrungsfrist)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    documents: Mapped[list["DocumentModel"]] = relationship("DocumentModel", back_populates="case", cascade="all, delete-orphan")
    findings: Mapped[list["FindingModel"]] = relationship("FindingModel", back_populates="case", cascade="all, delete-orphan")


class LegalBaseModel(Base):
    """Legal bases (Rechtsgrundlagen): DSGVO, BDSG, sector laws, agreements. Content is chunked and indexed in Weaviate for RAG."""
    __tablename__ = "legal_bases"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    short_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    applicability: Mapped[str] = mapped_column(String(20), nullable=False, default="always")  # "always" | "conditional"
    department_codes: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    case_types: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    internal_only: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class PlaybookModel(Base):
    __tablename__ = "playbooks"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    version: Mapped[str] = mapped_column(String(50), nullable=False)
    content: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    case_type: Mapped[str] = mapped_column(String(100), nullable=True)
    department: Mapped[str] = mapped_column(String(200), nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    revisions: Mapped[list["PlaybookRevisionModel"]] = relationship(
        "PlaybookRevisionModel", back_populates="playbook", cascade="all, delete-orphan", order_by="PlaybookRevisionModel.created_at.desc()"
    )


class PlaybookRevisionModel(Base):
    """Snapshot of playbook content on each PATCH; enables version history and rollback."""
    __tablename__ = "playbook_revisions"
    __table_args__ = (Index("ix_playbook_revisions_playbook_id_created_at", "playbook_id", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    playbook_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("playbooks.id", ondelete="CASCADE"), nullable=False)
    version: Mapped[str] = mapped_column(String(50), nullable=False)
    content: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    changed_by: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    playbook: Mapped["PlaybookModel"] = relationship("PlaybookModel", back_populates="revisions")


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
    type: Mapped[str] = mapped_column(String(50), nullable=False)  # vvt, screening, info_sheet_de, ...
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    format: Mapped[str] = mapped_column(String(20), nullable=False)  # docx, pdf, xlsx, doc
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    uploaded_by: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    storage_path: Mapped[str] = mapped_column(String(1000), nullable=False)  # path in MinIO or local FS
    content: Mapped[str] = mapped_column(Text, nullable=True)  # Extracted text content
    extraction_method: Mapped[str | None] = mapped_column(String(20), nullable=True)  # "text" | "ocr"
    extraction_status: Mapped[str] = mapped_column(String(20), nullable=False, default=DocumentExtractionStatus.PENDING)
    extraction_error: Mapped[str | None] = mapped_column(Text, nullable=True)  # Error message when extraction_status=failed
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


class FindingCommentModel(Base):
    """User comments on a finding (discussion / audit trail for status decisions)."""
    __tablename__ = "finding_comments"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    finding_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("findings.id", ondelete="CASCADE"), nullable=False)
    case_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("cases.id", ondelete="CASCADE"), nullable=False)
    author: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    user_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


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
    source_strategy: Mapped[str | None] = mapped_column(String(20), nullable=True)  # "full_text" | "rag"
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

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


class UserModel(Base):
    """User profile and preferences (current user via OIDC token or CURRENT_USER_ID or default)."""
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    oidc_sub: Mapped[str | None] = mapped_column(String(500), nullable=True, unique=True)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False, default="Standardnutzer")
    email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    role: Mapped[str] = mapped_column(String(20), nullable=False, default=UserRole.VIEWER)
    preferences: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class PromptTemplateModel(Base):
    """Versioned prompt template for LLM (check runner, VVT). One active version per key."""
    __tablename__ = "prompt_templates"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    key: Mapped[str] = mapped_column(String(100), nullable=False)
    version: Mapped[str] = mapped_column(String(50), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class ActivityLogModel(Base):
    """Audit log for case-related events (run_checks, finding_status_updated, etc.)."""
    __tablename__ = "activity_log"
    __table_args__ = (Index("ix_activity_log_case_id_created_at", "case_id", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    case_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("cases.id", ondelete="CASCADE"), nullable=False)
    event_type: Mapped[str] = mapped_column(String(80), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class RunChecksJobModel(Base):
    """One row per run-checks execution; status running/completed/failed for async feedback."""
    __tablename__ = "run_checks_jobs"
    __table_args__ = (Index("ix_run_checks_jobs_case_id_created_at", "case_id", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    case_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("cases.id", ondelete="CASCADE"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)  # running | completed | failed
    playbook_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("playbooks.id", ondelete="SET NULL"), nullable=True)
    playbook_name: Mapped[str] = mapped_column(String(200), nullable=False)
    strategies: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False, default=list)
    celery_task_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    findings_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    checks_total: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    checks_done: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    result_payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class DSBReportModel(Base):
    """Latest DSB report per case; overwritten on each generation."""
    __tablename__ = "dsb_reports"

    case_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("cases.id", ondelete="CASCADE"), primary_key=True)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    basis_document_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    basis_last_run_checks_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class DSBReportJobModel(Base):
    """One row per DSB report generation job; status running/completed/failed for async feedback."""
    __tablename__ = "dsb_report_jobs"
    __table_args__ = (Index("ix_dsb_report_jobs_case_id_created_at", "case_id", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    case_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("cases.id", ondelete="CASCADE"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)  # running | completed | failed
    celery_task_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class DSFAAssessmentModel(Base):
    """DSFA (Datenschutz-Folgenabschätzung, Art. 35 DSGVO) per case."""
    __tablename__ = "dsfa_assessments"

    case_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("cases.id", ondelete="CASCADE"), primary_key=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="draft")  # draft | finalized
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finalized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finalized_by: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class DSFAJobModel(Base):
    """Async DSFA generation job tracking."""
    __tablename__ = "dsfa_jobs"
    __table_args__ = (Index("ix_dsfa_jobs_case_id", "case_id"),)

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    case_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("cases.id", ondelete="CASCADE"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)  # running | completed | failed
    celery_task_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class FindingChatMessageModel(Base):
    """LLM chat messages per finding (finding remediation assistant)."""
    __tablename__ = "finding_chat_messages"
    __table_args__ = (Index("ix_finding_chat_messages_finding_id", "finding_id"),)

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    finding_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("findings.id", ondelete="CASCADE"), nullable=False)
    case_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("cases.id", ondelete="CASCADE"), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)  # user | assistant
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class DSRRequestModel(Base):
    """Betroffenenrechts-Anfragen (Art. 15–22 DSGVO)."""
    __tablename__ = "dsr_requests"
    __table_args__ = (
        Index("ix_dsr_requests_status", "status"),
        Index("ix_dsr_requests_response_deadline", "response_deadline"),
    )

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    request_type: Mapped[str] = mapped_column(String(50), nullable=False)  # access|rectification|erasure|portability|restriction|objection
    requestor_name: Mapped[str | None] = mapped_column(String(500), nullable=True)
    requestor_email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    department: Mapped[str | None] = mapped_column(String(200), nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="received")  # received|in_progress|response_sent|closed|denied
    assignee: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    received_at: Mapped[date] = mapped_column(Date, nullable=False)
    response_deadline: Mapped[date] = mapped_column(Date, nullable=False)
    responded_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    response_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    draft_response: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_notified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, default=None)  # Letzter Benachrichtigungsversand (Anti-Spam)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    activity_logs: Mapped[list["DSRActivityLogModel"]] = relationship("DSRActivityLogModel", back_populates="request", cascade="all, delete-orphan")


class DSRActivityLogModel(Base):
    """Aktivitätsprotokoll für DSR-Anfragen."""
    __tablename__ = "dsr_activity_log"
    __table_args__ = (Index("ix_dsr_activity_log_request_id", "request_id"),)

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    request_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("dsr_requests.id", ondelete="CASCADE"), nullable=False)
    event_type: Mapped[str] = mapped_column(String(80), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    request: Mapped["DSRRequestModel"] = relationship("DSRRequestModel", back_populates="activity_logs")


class DataBreachModel(Base):
    """Datenschutzverletzungen (Art. 33/34 DSGVO) – 72-Stunden-Meldepflicht."""
    __tablename__ = "data_breaches"
    __table_args__ = (
        Index("ix_data_breaches_status", "status"),
        Index("ix_data_breaches_discovered_at", "discovered_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    discovered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # 72h-Frist für Behördenmeldung (Art. 33 Abs. 1)
    notification_deadline: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    breach_type: Mapped[str] = mapped_column(String(100), nullable=False)  # confidentiality|integrity|availability
    affected_data_categories: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    affected_persons_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    department: Mapped[str | None] = mapped_column(String(200), nullable=True)
    assignee: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="discovered")
    # discovered | assessed | reported_to_authority | reported_to_subjects | closed | no_notification_required
    risk_level: Mapped[str | None] = mapped_column(String(20), nullable=True)  # low|medium|high|critical
    authority_notified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    subjects_notified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    authority_reference: Mapped[str | None] = mapped_column(String(200), nullable=True)
    measures_taken: Mapped[str | None] = mapped_column(Text, nullable=True)
    draft_notification: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_notified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, default=None)  # Letzter Benachrichtigungsversand (Anti-Spam)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    activity_logs: Mapped[list["DataBreachActivityLogModel"]] = relationship(
        "DataBreachActivityLogModel", back_populates="breach", cascade="all, delete-orphan"
    )


class DataBreachActivityLogModel(Base):
    """Aktivitätsprotokoll für Datenpannen."""
    __tablename__ = "data_breach_activity_log"
    __table_args__ = (Index("ix_data_breach_activity_log_breach_id", "breach_id"),)

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    breach_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("data_breaches.id", ondelete="CASCADE"), nullable=False)
    event_type: Mapped[str] = mapped_column(String(80), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    breach: Mapped["DataBreachModel"] = relationship("DataBreachModel", back_populates="activity_logs")


class AVVContractModel(Base):
    """Auftragsverarbeitungsverträge (Art. 28 DSGVO)."""
    __tablename__ = "avv_contracts"
    __table_args__ = (
        Index("ix_avv_contracts_status", "status"),
        Index("ix_avv_contracts_partner_name", "partner_name"),
    )

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    partner_name: Mapped[str] = mapped_column(String(500), nullable=False)
    partner_type: Mapped[str] = mapped_column(String(50), nullable=False, default="processor")  # processor|sub_processor
    subject_matter: Mapped[str | None] = mapped_column(Text, nullable=True)
    department: Mapped[str | None] = mapped_column(String(200), nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending")
    # pending | under_review | signed | expired | terminated
    contract_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    expiry_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    assignee: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    storage_path: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    document_name: Mapped[str | None] = mapped_column(String(500), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    check_result: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    # Supplier-Risikobewertung (Feature: AVV-Risikoscoring)
    risk_score: Mapped[int | None] = mapped_column(Integer, nullable=True)           # 0-100
    risk_level: Mapped[str | None] = mapped_column(String(20), nullable=True)        # low | medium | high | critical
    risk_assessment: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)  # detaillierte Bewertung
    risk_assessed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_notified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, default=None)  # Letzter Benachrichtigungsversand (Anti-Spam)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class TOMModel(Base):
    """Technisch-Organisatorische Maßnahmen (Art. 32 DSGVO)."""
    __tablename__ = "tom_measures"
    __table_args__ = (
        Index("ix_tom_measures_category", "category"),
        Index("ix_tom_measures_status", "implementation_status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    # access_control|encryption|pseudonymization|availability|integrity|confidentiality|resilience|testing|incident_response|other
    implementation_status: Mapped[str] = mapped_column(String(30), nullable=False, default="planned")
    # planned | in_progress | implemented | not_applicable
    responsible: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    review_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    evidence: Mapped[str | None] = mapped_column(Text, nullable=True)
    department_codes: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class TOMAttachmentModel(Base):
    """File attachments for TOM measures (evidence files)."""
    __tablename__ = "tom_attachments"
    __table_args__ = (
        Index("ix_tom_attachments_tom_id", "tom_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tom_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("tom_measures.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    format: Mapped[str] = mapped_column(String(20), nullable=False)  # docx | pdf | xlsx | doc
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    storage_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    uploaded_by: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class PrivacyPolicyModel(Base):
    """Generierte Datenschutzerklärungen (Art. 13/14 DSGVO)."""
    __tablename__ = "privacy_policies"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(500), nullable=False, default="Datenschutzerklärung")
    content_markdown: Mapped[str] = mapped_column(Text, nullable=False, default="")
    version_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    org_name: Mapped[str | None] = mapped_column(String(300), nullable=True)
    department: Mapped[str | None] = mapped_column(String(200), nullable=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_by: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class WebhookConfigModel(Base):
    """Ausgehende Webhook-Konfigurationen für Event-Benachrichtigungen."""
    __tablename__ = "webhook_configs"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    url: Mapped[str] = mapped_column(String(2000), nullable=False)
    secret: Mapped[str | None] = mapped_column(String(500), nullable=True)  # HMAC-Secret für Signatur
    events: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False, default=list)
    # Events: case_status_changed, finding_created, finding_status_changed, data_breach_created, dsr_created
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_by: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    deliveries: Mapped[list["WebhookDeliveryLogModel"]] = relationship(
        "WebhookDeliveryLogModel", back_populates="webhook", cascade="all, delete-orphan"
    )


class WebhookDeliveryLogModel(Base):
    """Protokoll aller ausgehenden Webhook-Zustellversuche."""
    __tablename__ = "webhook_delivery_logs"
    __table_args__ = (Index("ix_webhook_delivery_logs_webhook_id", "webhook_id"),)

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    webhook_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("webhook_configs.id", ondelete="CASCADE"), nullable=False)
    event_type: Mapped[str] = mapped_column(String(80), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=WebhookDeliveryStatus.PENDING)
    http_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    webhook: Mapped["WebhookConfigModel"] = relationship("WebhookConfigModel", back_populates="deliveries")


class CaseTemplateModel(Base):
    """Vorgangs-Vorlagen für häufig wiederkehrende Verarbeitungstätigkeiten."""
    __tablename__ = "case_templates"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    case_type: Mapped[str] = mapped_column(String(100), nullable=False)
    department: Mapped[str | None] = mapped_column(String(200), nullable=True)
    language: Mapped[str] = mapped_column(String(20), nullable=False, default="de")
    processing_context: Mapped[str | None] = mapped_column(String(500), nullable=True)
    special_category_data: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    international_transfer: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_builtin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_by: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


