"""Legal base (Rechtsgrundlagen) ORM model."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, String, Text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models._db.base import Base


class LegalBaseModel(Base):
    """Legal bases (Rechtsgrundlagen): DSGVO, BDSG, sector laws, agreements. Content is chunked and indexed in Weaviate for RAG."""

    __tablename__ = "legal_bases"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    short_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    applicability: Mapped[str] = mapped_column(
        String(20), nullable=False, default="always"
    )
    department_codes: Mapped[list[str] | None] = mapped_column(
        ARRAY(String), nullable=True
    )
    case_types: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    internal_only: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )
