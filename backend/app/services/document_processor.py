"""Text extraction from documents (PDF, DOCX, XLSX).

Goals beyond plain text dumping:
- Preserve structure: PDFs are extracted as Markdown (layout/tables) via pymupdf4llm;
  DOCX tables and XLSX sheets are emitted as Markdown tables with column letters, so that
  downstream LLM evidence like "Sheet X, Spalte C, Zeile 12" stays meaningful.
- Mixed scanned PDFs: decide per page whether to OCR (Ollama Vision), OCR'ing only the
  sparse pages, in parallel.
- Quality signals: report char/page counts and the OCR page ratio so weak extractions can
  be flagged downstream.
"""
import base64
import io
import logging
import shutil
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import docx
import fitz  # PyMuPDF
import httpx
import openpyxl
from openpyxl.utils import get_column_letter

from app.config import settings

logger = logging.getLogger(__name__)

EXTRACTION_METHOD_TEXT: Literal["text"] = "text"
EXTRACTION_METHOD_OCR: Literal["ocr"] = "ocr"


class UnsupportedDocumentError(ValueError):
    """Raised when a document format cannot be extracted (e.g. legacy .doc without a converter)."""


@dataclass
class ExtractionResult:
    """Result of text extraction.

    Args:
        text: Extracted text (Markdown for PDF/DOCX/XLSX).
        extraction_method: "text" (digital) or "ocr" (at least one page via vision OCR).
        char_count: Length of the extracted text (quality signal).
        page_count: Number of pages (PDF) or 0 for non-paged formats.
        ocr_page_ratio: Fraction of pages extracted via OCR (0.0 = fully digital).
    """
    text: str
    extraction_method: Literal["text", "ocr"]
    char_count: int = 0
    page_count: int = 0
    ocr_page_ratio: float = 0.0


OCR_PROMPT = (
    "Extrahiere den gesamten Text aus diesem Bild als Markdown. "
    "Erhalte dabei Tabellen als Markdown-Tabellen und die Lesereihenfolge. "
    "Gib nur den extrahierten Inhalt zurück, keine Erklärungen oder Überschriften."
)


def _pdf_page_to_png_bytes(content: bytes, page_index: int, dpi: int = 150) -> bytes:
    """Render a single PDF page to PNG bytes."""
    with fitz.open(stream=content, filetype="pdf") as doc:
        page = doc[page_index]
        pix = page.get_pixmap(dpi=dpi, alpha=False)
        return pix.tobytes("png")


def _ollama_chat_api_url() -> str:
    """Return the Ollama native chat API URL (always at :11434/api/chat, not /v1)."""
    base = (settings.ollama_base_url or "").rstrip("/")
    if base.endswith("/v1"):
        base = base[:-3]
    return f"{base}/api/chat"


def _pdf_markdown(content: bytes, pages: list[int] | None = None) -> str:
    """Extract layout-/table-preserving Markdown from a PDF via pymupdf4llm.

    Falls back to plain PyMuPDF get_text on any failure. ``pages`` (0-based) limits
    extraction to specific pages; None = whole document.
    """
    try:
        import pymupdf4llm

        with fitz.open(stream=content, filetype="pdf") as doc:
            return pymupdf4llm.to_markdown(doc, pages=pages, show_progress=False).strip()
    except Exception as exc:
        logger.warning("pymupdf4llm markdown extraction failed, falling back to get_text: %s", exc)
        try:
            with fitz.open(stream=content, filetype="pdf") as doc:
                indices = pages if pages is not None else range(len(doc))
                return "\n".join(doc[i].get_text() for i in indices).strip()
        except Exception as exc2:
            logger.warning("PyMuPDF get_text fallback also failed: %s", exc2)
            return ""


def _ocr_pages(content: bytes, page_indices: list[int]) -> dict[int, str]:
    """OCR the given PDF pages concurrently via Ollama Vision. Returns {page_index: text}."""
    chat_url = _ollama_chat_api_url()
    timeout = httpx.Timeout(settings.ollama_timeout_seconds, connect=10.0)
    dpi = getattr(settings, "ocr_dpi", 150)
    concurrency = max(1, getattr(settings, "ocr_concurrency", 4))

    def _ocr_one(i: int) -> tuple[int, str]:
        try:
            png_bytes = _pdf_page_to_png_bytes(content, i, dpi=dpi)
            payload = {
                "model": settings.ollama_ocr_model,
                "messages": [
                    {
                        "role": "user",
                        "content": OCR_PROMPT,
                        "images": [base64.b64encode(png_bytes).decode()],
                    }
                ],
                "stream": False,
            }
            resp = httpx.post(chat_url, json=payload, timeout=timeout)
            resp.raise_for_status()
            data = resp.json()
            return i, ((data.get("message") or {}).get("content") or "").strip()
        except Exception as exc:
            logger.warning("Ollama OCR failed for page %s: %s", i + 1, exc)
            return i, ""

    results: dict[int, str] = {}
    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        for i, text in pool.map(_ocr_one, page_indices):
            results[i] = text
    return results


def extract_text_from_pdf(content: bytes) -> ExtractionResult:
    """
    Extract text from PDF as Markdown.

    Uses PyMuPDF to detect sparse (likely scanned) pages. When OCR is enabled, only the
    sparse pages are OCR'd via Ollama Vision (per-page, in parallel) and merged with the
    digital pages; fully digital PDFs skip OCR entirely.
    """
    with fitz.open(stream=content, filetype="pdf") as doc:
        num_pages = len(doc)
        page_digital = [doc[i].get_text() for i in range(num_pages)]

    if num_pages == 0:
        return ExtractionResult(text="", extraction_method=EXTRACTION_METHOD_TEXT)

    min_chars = settings.ocr_min_chars_per_page
    sparse_pages = [i for i, t in enumerate(page_digital) if len((t or "").strip()) < min_chars]

    # No OCR needed (or disabled): return full-document Markdown.
    if not settings.ollama_ocr_enabled or not sparse_pages:
        text = _pdf_markdown(content) or "\n".join(page_digital)
        return ExtractionResult(
            text=text,
            extraction_method=EXTRACTION_METHOD_TEXT,
            char_count=len(text),
            page_count=num_pages,
            ocr_page_ratio=0.0,
        )

    # Decide which pages to OCR.
    if getattr(settings, "ocr_per_page", True):
        ocr_pages = set(sparse_pages)
    else:
        avg = sum(len((t or "").strip()) for t in page_digital) / num_pages
        ocr_pages = set(range(num_pages)) if avg < min_chars else set()

    if not ocr_pages:
        text = _pdf_markdown(content) or "\n".join(page_digital)
        return ExtractionResult(
            text=text,
            extraction_method=EXTRACTION_METHOD_TEXT,
            char_count=len(text),
            page_count=num_pages,
            ocr_page_ratio=0.0,
        )

    # Cap OCR work to avoid memory/time exhaustion on huge scans.
    max_ocr_pages = getattr(settings, "ocr_max_pages", 200)
    ocr_targets = sorted(ocr_pages)[:max_ocr_pages]
    if len(ocr_pages) > max_ocr_pages:
        logger.warning("OCR limited to first %d of %d candidate pages", max_ocr_pages, len(ocr_pages))
    ocr_results = _ocr_pages(content, ocr_targets)

    parts: list[str] = []
    used_ocr = 0
    for i in range(num_pages):
        ocr_text = ocr_results.get(i, "")
        if i in ocr_pages and ocr_text.strip():
            parts.append(ocr_text)
            used_ocr += 1
        else:
            # Digital (or OCR-failed) page → use layout-preserving Markdown for this page.
            parts.append(_pdf_markdown(content, pages=[i]) or (page_digital[i] or ""))
    text = "\n\n".join(p for p in parts if p)
    method = EXTRACTION_METHOD_OCR if used_ocr > 0 else EXTRACTION_METHOD_TEXT
    return ExtractionResult(
        text=text,
        extraction_method=method,
        char_count=len(text),
        page_count=num_pages,
        ocr_page_ratio=(used_ocr / num_pages) if num_pages else 0.0,
    )


def _docx_table_to_markdown(table) -> str:
    """Render a python-docx table as a Markdown table (first row = header)."""
    rows = []
    for row in table.rows:
        cells = [(cell.text or "").replace("\n", " ").replace("|", "\\|").strip() for cell in row.cells]
        rows.append(cells)
    if not rows:
        return ""
    width = max(len(r) for r in rows)
    rows = [r + [""] * (width - len(r)) for r in rows]
    header = "| " + " | ".join(rows[0]) + " |"
    sep = "| " + " | ".join(["---"] * width) + " |"
    body = ["| " + " | ".join(r) + " |" for r in rows[1:]]
    return "\n".join([header, sep, *body])


def extract_text_from_docx(content: bytes) -> str:
    """Extract text from DOCX bytes; tables are rendered as Markdown tables."""
    doc = docx.Document(io.BytesIO(content))
    parts: list[str] = []
    for para in doc.paragraphs:
        if para.text and para.text.strip():
            parts.append(para.text)
    for table in doc.tables:
        md = _docx_table_to_markdown(table)
        if md:
            parts.append(md)
    return "\n".join(parts)


def extract_text_from_xlsx(content: bytes) -> str:
    """Extract text from XLSX bytes as one Markdown table per sheet.

    Column letters (A, B, C, …) form the header row and empty cells are preserved as empty
    columns, so column alignment — and thus coordinate-based evidence — stays intact.
    """
    wb = openpyxl.load_workbook(io.BytesIO(content), data_only=True)
    out: list[str] = []
    for sheet in wb.sheetnames:
        ws = wb[sheet]
        out.append(f"--- Sheet: {sheet} ---")
        rows = list(ws.iter_rows(values_only=True))
        max_cols = max((len(r) for r in rows), default=0)
        if max_cols == 0:
            continue
        col_header = [get_column_letter(c + 1) for c in range(max_cols)]
        out.append("| " + " | ".join(col_header) + " |")
        out.append("| " + " | ".join(["---"] * max_cols) + " |")
        for r in rows:
            cells = ["" if c is None else str(c).replace("\n", " ").replace("|", "\\|") for c in r]
            cells += [""] * (max_cols - len(cells))
            out.append("| " + " | ".join(cells) + " |")
    return "\n".join(out)


def extract_text_from_doc(content: bytes) -> str:
    """Extract text from a legacy .doc (OLE2) file via LibreOffice or antiword if available.

    Raises UnsupportedDocumentError with actionable guidance when no converter is installed,
    instead of silently returning empty text.
    """
    if shutil.which("antiword"):
        try:
            return subprocess.run(
                ["antiword", "-"], input=content, capture_output=True, timeout=120
            ).stdout.decode("utf-8", errors="replace")
        except Exception as exc:
            logger.warning("antiword .doc extraction failed: %s", exc)
    soffice = shutil.which("soffice") or shutil.which("libreoffice")
    if soffice:
        try:
            with tempfile.TemporaryDirectory() as tmp:
                src = Path(tmp) / "in.doc"
                src.write_bytes(content)
                subprocess.run(
                    [soffice, "--headless", "--convert-to", "docx", "--outdir", tmp, str(src)],
                    capture_output=True, timeout=180,
                )
                out = Path(tmp) / "in.docx"
                if out.exists():
                    return extract_text_from_docx(out.read_bytes())
        except Exception as exc:
            logger.warning("LibreOffice .doc conversion failed: %s", exc)
    raise UnsupportedDocumentError(
        "Legacy .doc files require a converter (LibreOffice/soffice or antiword) which is not "
        "available. Please upload the document as .docx or PDF."
    )


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
            return ExtractionResult(text=text, extraction_method=EXTRACTION_METHOD_TEXT, char_count=len(text))
        except Exception:
            logger.exception("DOCX text extraction failed", extra={"filename": filename})
            raise
    if filename_lower.endswith(".xlsx"):
        try:
            text = extract_text_from_xlsx(content)
            return ExtractionResult(text=text, extraction_method=EXTRACTION_METHOD_TEXT, char_count=len(text))
        except Exception:
            logger.exception("XLSX text extraction failed", extra={"filename": filename})
            raise
    if filename_lower.endswith(".doc"):
        text = extract_text_from_doc(content)
        return ExtractionResult(text=text, extraction_method=EXTRACTION_METHOD_TEXT, char_count=len(text))
    try:
        text = content.decode("utf-8")
        return ExtractionResult(text=text, extraction_method=EXTRACTION_METHOD_TEXT, char_count=len(text))
    except UnicodeDecodeError:
        logger.debug("UTF-8 decode failed for %s", filename)
        return ExtractionResult(text="", extraction_method=EXTRACTION_METHOD_TEXT)
