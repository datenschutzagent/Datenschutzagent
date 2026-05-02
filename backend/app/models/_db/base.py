"""SQLAlchemy declarative base shared by all domain models."""
import uuid

from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Declarative base for all models."""
    type_annotation_map = {
        uuid.UUID: PG_UUID(as_uuid=True),
    }
