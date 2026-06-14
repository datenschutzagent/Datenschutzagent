"""ORM models for Auftragsverarbeitungsverträge (Art. 28 DSGVO)."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import (
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
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models._db.base import Base


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
