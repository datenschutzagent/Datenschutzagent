"""Text extraction from documents (PDF, DOCX, XLSX). PDFs with little text use Ollama Vision OCR fallback."""
import io
import logging
from dataclasses import dataclass
from typing import Literal

import fitz  # PyMuPDF
import docx
import openpyxl

from app.config import settings

logger = logging.getLogger(__name__)

EXTRACTION_METHOD_TEXT: Literal["text"] = "text"
EXTRACTION_METHOD_OCR: Literal["ocr"] = "ocr"


@dataclass
class ExtractionResult:
    """Result of text extraction; includes whether OCR was used."""
    text: str
    extraction_method: Literal["text", "ocr"]


OCR_PROMPT = (
    "Extrahiere den gesamten Text aus diesem Bild. "
    "Gib nur den extrahierten Text zurück, keine Erklärungen oder Überschriften."
)


def _pdf_page_to_png_bytes(content: bytes, page_index: int, dpi: int = 150) -> bytes:
    """Render a single PDF page to PNG bytes."""
    with fitz.open(stream=content, filetype="pdf") as doc:
        page = doc[page_index]
        pix = page.get_pixmap(dpi=dpi, alpha=False)
        return pix.tobytes("png")


def _extract_text_from_pdf_via_ollama(content: bytes) -> str:
    """
    Extract text from PDF using Ollama Vision model (e.g. qwen2.5-vl).
    Renders each page to PNG and sends to the model. On failure returns empty string.
    """
    try:
        import ollama
    except ImportError:
        logger.warning("ollama package not available; OCR fallback disabled")
        return ""

    # Ollama client: host without /v1 (native API is on :11434)
    base = (settings.ollama_base_url or "").rstrip("/")
    if base.endswith("/v1"):
        base = base[:-3]
    host = base or "http://localhost:11434"

    client = ollama.Client(host=host)
    dpi = getattr(settings, "ocr_dpi", 150)

    with fitz.open(stream=content, filetype="pdf") as doc:
        page_texts: list[str] = []
        for i in range(len(doc)):
            try:
                png_bytes = _pdf_page_to_png_bytes(content, i, dpi=dpi)
                response = client.chat(
                    model=settings.ollama_ocr_model,
                    messages=[
                        {
                            "role": "user",
                            "content": OCR_PROMPT,
                            "images": [png_bytes],
                        }
                    ],
                )
                content_msg = (response.get("message") or {}).get("content") or ""
                page_texts.append(content_msg.strip())
            except Exception as e:
                logger.warning("Ollama OCR failed for page %s: %s", i + 1, e)
                page_texts.append("")
        return "\n\n".join(page_texts)


def extract_text_from_pdf(content: bytes) -> ExtractionResult:
    """
    Extract text from PDF. Uses PyMuPDF first; if text is sparse (e.g. scanned PDF),
    falls back to Ollama Vision OCR when ollama_ocr_enabled.
    """
    with fitz.open(stream=content, filetype="pdf") as doc:
        text = ""
        for page in doc:
            text += page.get_text() + "\n"
        num_pages = len(doc)
    avg_chars_per_page = (len(text.strip()) / num_pages) if num_pages else 0

    if (
        settings.ollama_ocr_enabled
        and num_pages > 0
        and avg_chars_per_page < settings.ocr_min_chars_per_page
    ):
        ocr_text = _extract_text_from_pdf_via_ollama(content)
        if ocr_text.strip():
            return ExtractionResult(text=ocr_text, extraction_method=EXTRACTION_METHOD_OCR)
        # OCR failed or returned nothing; keep PyMuPDF text
        logger.debug("Ollama OCR returned no text; using PyMuPDF extraction")
    return ExtractionResult(text=text, extraction_method=EXTRACTION_METHOD_TEXT)


def extract_text_from_docx(content: bytes) -> str:
    """Extract text from DOCX bytes."""
    doc = docx.Document(io.BytesIO(content))
    text = []
    for para in doc.paragraphs:
        text.append(para.text)
    for table in doc.tables:
        for row in table.rows:
            row_text = [cell.text for cell in row.cells]
            text.append(" | ".join(row_text))
    return "\n".join(text)


def extract_text_from_xlsx(content: bytes) -> str:
    """Extract text from XLSX bytes (all sheets)."""
    wb = openpyxl.load_workbook(io.BytesIO(content), data_only=True)
    text = []
    for sheet in wb.sheetnames:
        ws = wb[sheet]
        text.append(f"--- Sheet: {sheet} ---")
        for row in ws.iter_rows(values_only=True):
            row_text = [str(cell) for cell in row if cell is not None]
            if row_text:
                text.append("\t".join(row_text))
    return "\n".join(text)


def extract_text(filename: str, content: bytes) -> ExtractionResult:
    """
    Dispatcher for text extraction. Returns ExtractionResult with text and
    extraction_method ("text" or "ocr" for PDFs that used Ollama Vision).
    """
    filename_lower = filename.lower()
    if filename_lower.endswith(".pdf"):
        return extract_text_from_pdf(content)
    if filename_lower.endswith(".docx"):
        try:
            text = extract_text_from_docx(content)
            return ExtractionResult(text=text, extraction_method=EXTRACTION_METHOD_TEXT)
        except Exception:
            logger.exception("DOCX text extraction failed", extra={"filename": filename})
            raise
    if filename_lower.endswith(".xlsx"):
        try:
            text = extract_text_from_xlsx(content)
            return ExtractionResult(text=text, extraction_method=EXTRACTION_METHOD_TEXT)
        except Exception:
            logger.exception("XLSX text extraction failed", extra={"filename": filename})
            raise
    try:
        text = content.decode("utf-8")
        return ExtractionResult(text=text, extraction_method=EXTRACTION_METHOD_TEXT)
    except UnicodeDecodeError:
        logger.debug("UTF-8 decode failed for %s", filename)
        return ExtractionResult(text="", extraction_method=EXTRACTION_METHOD_TEXT)
