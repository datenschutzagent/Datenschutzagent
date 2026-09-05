"""Global API audit log model – records mutating API calls and privacy-relevant reads."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import BigInteger, DateTime, Identity, Index, Integer, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models._db.base import Base


class APIAuditLogModel(Base):
    """Append-only record of an audited HTTP request.

    Rows form a hash chain: ``entry_hash = sha256(prev_hash || fields)`` where
    ``prev_hash`` is the ``entry_hash`` of the previous row in ``seq`` order. Editing or
    deleting a row breaks the chain, which ``app.services.audit_service.verify_audit_chain``
    (CLI: ``python -m app.cli audit verify``) detects.

    user_id has no FK so the log survives user deletion (DSGVO retention).
    No request body or PII is stored – only endpoint, method, status, identity and, for
    audited reads (document content/download, exports), the resource id.
    """

    __tablename__ = "api_audit_log"
    __table_args__ = (
        Index("ix_api_audit_log_user_id_timestamp", "user_id", "timestamp"),
        Index("ix_api_audit_log_request_id", "request_id"),
        Index("ix_api_audit_log_seq", "seq", unique=True),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    # Monotonic insert order for the hash chain (identity column, never reused).
    seq: Mapped[int] = mapped_column(BigInteger, Identity(always=True), nullable=False)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True
    )
    endpoint: Mapped[str] = mapped_column(String(255), nullable=False)
    method: Mapped[str] = mapped_column(String(10), nullable=False)
    status_code: Mapped[int] = mapped_column(Integer, nullable=False)
    request_id: Mapped[str] = mapped_column(String(36), nullable=False, default="-")
    # Concrete object for audited reads (e.g. the document id); NULL for mutations,
    # whose endpoint already carries {id} placeholders.
    resource_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    prev_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # NULL only for rows written before the chain existed (pre-migration).
    entry_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
