"""Document-related schemas."""
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from .common import DocumentTypeEnum, DocumentFormatEnum, ExtractionMethodEnum, ExtractionStatusEnum


class DocumentResponse(BaseModel):
    id: UUID
    name: str
    type: DocumentTypeEnum
    version: int
    uploaded_at: datetime
    uploaded_by: str
    size_bytes: int
    format: DocumentFormatEnum
    case_id: UUID
    extraction_method: ExtractionMethodEnum | None = None
    extraction_status: ExtractionStatusEnum | None = None
    extraction_error: str | None = None
    extraction_char_count: int | None = None
    extraction_page_count: int | None = None
    extraction_ocr_ratio: float | None = None
    extraction_ocr_low_quality_pages: int | None = None

    model_config = {"from_attributes": True}


class DocumentUpdate(BaseModel):
    """Partial update for document (e.g. extracted content for LLM/checks)."""
    content: str | None = None


class DocumentCommentCreate(BaseModel):
    text: str = Field(..., min_length=1)


class DocumentCommentResponse(BaseModel):
    id: UUID
    document_id: UUID
    case_id: UUID
    author: str
    user_id: UUID | None = None
    text: str
    created_at: datetime

    model_config = {"from_attributes": True}
