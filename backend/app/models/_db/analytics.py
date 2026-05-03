"""Tagliche Maturity-Snapshots fuer den Compliance-Reife-Trend pro Abteilung."""
import uuid
from datetime import date, datetime, timezone

from sqlalchemy import Date, DateTime, Float, Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models._db.base import Base


class ComplianceMaturitySnapshotModel(Base):
    """Ein Snapshot pro Department und Tag. Befuellt durch taeglichen Celery-Beat-Job."""
    __tablename__ = "compliance_maturity_snapshots"
    __table_args__ = (
        UniqueConstraint("department", "snapshot_date", name="uq_maturity_dept_date"),
        Index("ix_maturity_snapshot_date", "snapshot_date"),
    )

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    department: Mapped[str] = mapped_column(String(200), nullable=False)
    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False)
    vvt_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    dsfa_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    avv_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    tom_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    velocity_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    composite_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
