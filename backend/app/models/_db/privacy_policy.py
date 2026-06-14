"""ORM model for Privacy Policies (Art. 13/14 DSGVO)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models._db.base import Base

if TYPE_CHECKING:
    from app.models._db.case import CaseModel


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
