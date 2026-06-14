"""ORM model for Case Templates."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models._db.base import Base


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
