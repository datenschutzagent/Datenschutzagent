"""SQLAlchemy ORM models."""
import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from datetime import timezone


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
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="intake")
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
    extraction_status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")  # pending | processing | done | failed
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
    )

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    case_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("cases.id", ondelete="CASCADE"), nullable=False)
    document_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("documents.id", ondelete="SET NULL"), nullable=True)
    check_name: Mapped[str] = mapped_column(String(300), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="open")
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    evidence: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, default=list)
    recommendation: Mapped[str] = mapped_column(Text, nullable=False, default="")
    source_strategy: Mapped[str | None] = mapped_column(String(20), nullable=True)  # "full_text" | "rag"
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    case: Mapped["CaseModel"] = relationship("CaseModel", back_populates="findings")


class UserModel(Base):
    """User profile and preferences (current user via OIDC token or CURRENT_USER_ID or default)."""
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    oidc_sub: Mapped[str | None] = mapped_column(String(500), nullable=True, unique=True)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False, default="Standardnutzer")
    email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="viewer")  # viewer | editor | admin
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


def orm_to_user_response(orm: UserModel) -> dict[str, Any]:
    """Map UserModel to API response shape."""
    return {
        "id": orm.id,
        "display_name": orm.display_name,
        "email": orm.email,
        "role": orm.role,
        "preferences": orm.preferences or {},
        "created_at": orm.created_at,
        "updated_at": orm.updated_at,
    }


def orm_to_activity_response(orm: ActivityLogModel) -> dict[str, Any]:
    """Map ActivityLogModel to API response shape (snake_case)."""
    return {
        "id": orm.id,
        "case_id": orm.case_id,
        "event_type": orm.event_type,
        "payload": orm.payload or {},
        "created_at": orm.created_at,
    }


def orm_to_document_comment_response(orm: DocumentCommentModel) -> dict[str, Any]:
    """Map DocumentCommentModel to API response shape (snake_case)."""
    return {
        "id": orm.id,
        "document_id": orm.document_id,
        "case_id": orm.case_id,
        "author": orm.author,
        "user_id": orm.user_id,
        "text": orm.text,
        "created_at": orm.created_at,
    }


def orm_to_document_response(orm: DocumentModel) -> dict[str, Any]:
    """Map DocumentModel to API response shape (snake_case)."""
    return {
        "id": orm.id,
        "name": orm.name,
        "type": orm.type,
        "version": orm.version,
        "uploaded_at": orm.uploaded_at,
        "uploaded_by": orm.uploaded_by,
        "size_bytes": orm.size_bytes,
        "format": orm.format,
        "case_id": orm.case_id,
        "extraction_method": orm.extraction_method,
        "extraction_status": orm.extraction_status,
        "extraction_error": orm.extraction_error,
    }


def orm_to_finding_response(orm: FindingModel) -> dict[str, Any]:
    """Map FindingModel to API response shape."""
    return {
        "id": orm.id,
        "check_name": orm.check_name,
        "severity": orm.severity,
        "status": orm.status,
        "category": orm.category,
        "description": orm.description,
        "evidence": orm.evidence or [],
        "recommendation": orm.recommendation,
        "document_id": orm.document_id,
        "case_id": orm.case_id,
        "source_strategy": orm.source_strategy,
        "due_date": orm.due_date,
    }


def orm_to_finding_comment_response(orm: FindingCommentModel) -> dict[str, Any]:
    """Map FindingCommentModel to API response shape (snake_case)."""
    return {
        "id": orm.id,
        "finding_id": orm.finding_id,
        "case_id": orm.case_id,
        "author": orm.author,
        "user_id": orm.user_id,
        "text": orm.text,
        "created_at": orm.created_at,
    }


def orm_to_case_response(orm: CaseModel) -> dict[str, Any]:
    """Map CaseModel to API response with documents and findings. Documents sorted by type, then version (v1, v2, ...)."""
    docs_sorted = sorted(orm.documents, key=lambda d: (d.type, d.version))
    return {
        "id": orm.id,
        "title": orm.title,
        "department": orm.department,
        "case_type": orm.case_type,
        "status": orm.status,
        "language": orm.language,
        "created_at": orm.created_at,
        "updated_at": orm.updated_at,
        "created_by": orm.created_by,
        "assignee": orm.assignee,
        "playbook_version": orm.playbook_version,
        "processing_context": orm.processing_context,
        "special_category_data": orm.special_category_data,
        "international_transfer": orm.international_transfer,
        "deadline": orm.deadline,
        "auto_run_checks": orm.auto_run_checks,
        "archived_at": orm.archived_at,
        "retention_months": orm.retention_months,
        "documents": [orm_to_document_response(d) for d in docs_sorted],
        "findings": [orm_to_finding_response(f) for f in orm.findings],
    }


def orm_to_legal_base_response(orm: LegalBaseModel) -> dict[str, Any]:
    """Map LegalBaseModel to API response (snake_case)."""
    return {
        "id": orm.id,
        "title": orm.title,
        "short_name": orm.short_name,
        "content": orm.content or "",
        "applicability": orm.applicability,
        "department_codes": orm.department_codes or [],
        "case_types": orm.case_types or [],
        "internal_only": orm.internal_only,
        "created_at": orm.created_at,
        "updated_at": orm.updated_at,
    }


def orm_to_playbook_revision_response(orm: "PlaybookRevisionModel") -> dict[str, Any]:
    """Map PlaybookRevisionModel to API response."""
    return {
        "id": orm.id,
        "playbook_id": orm.playbook_id,
        "version": orm.version,
        "content": orm.content,
        "changed_by": orm.changed_by,
        "created_at": orm.created_at,
    }


def orm_to_playbook_response(orm: PlaybookModel) -> dict[str, Any]:
    """Map PlaybookModel to API response."""
    return {
        "id": orm.id,
        "name": orm.name,
        "version": orm.version,
        "content": orm.content,
        "case_type": orm.case_type,
        "department": orm.department,
        "is_active": orm.is_active,
        "created_at": orm.created_at,
    }


def orm_to_prompt_template_response(orm: PromptTemplateModel) -> dict[str, Any]:
    """Map PromptTemplateModel to API response."""
    return {
        "id": orm.id,
        "key": orm.key,
        "version": orm.version,
        "content": orm.content,
        "is_active": orm.is_active,
        "created_at": orm.created_at,
    }
