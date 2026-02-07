"""SQLAlchemy ORM models."""
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Declarative base for all models."""
    type_annotation_map = {
        uuid.UUID: PG_UUID(as_uuid=True),
    }


class CaseModel(Base):
    __tablename__ = "cases"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    department: Mapped[str] = mapped_column(String(200), nullable=False)
    case_type: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="intake")
    language: Mapped[str] = mapped_column(String(20), nullable=False, default="de")
    created_by: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    assignee: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    playbook_version: Mapped[str] = mapped_column(String(50), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    documents: Mapped[list["DocumentModel"]] = relationship("DocumentModel", back_populates="case", cascade="all, delete-orphan")
    findings: Mapped[list["FindingModel"]] = relationship("FindingModel", back_populates="case", cascade="all, delete-orphan")


class PlaybookModel(Base):
    __tablename__ = "playbooks"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    version: Mapped[str] = mapped_column(String(50), nullable=False)
    content: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    case_type: Mapped[str] = mapped_column(String(100), nullable=True)
    department: Mapped[str] = mapped_column(String(200), nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class DocumentModel(Base):
    __tablename__ = "documents"

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
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

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
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class FindingModel(Base):
    __tablename__ = "findings"

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
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)


class PromptTemplateModel(Base):
    """Versioned prompt template for LLM (check runner, VVT). One active version per key."""
    __tablename__ = "prompt_templates"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    key: Mapped[str] = mapped_column(String(100), nullable=False)
    version: Mapped[str] = mapped_column(String(50), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class ActivityLogModel(Base):
    """Audit log for case-related events (run_checks, finding_status_updated, etc.)."""
    __tablename__ = "activity_log"
    __table_args__ = (Index("ix_activity_log_case_id_created_at", "case_id", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    case_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("cases.id", ondelete="CASCADE"), nullable=False)
    event_type: Mapped[str] = mapped_column(String(80), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


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
        "documents": [orm_to_document_response(d) for d in docs_sorted],
        "findings": [orm_to_finding_response(f) for f in orm.findings],
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
