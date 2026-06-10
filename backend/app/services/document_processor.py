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
from docx.oxml.ns import qn
from lxml import etree
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


def _pdf_markdown_pages(content: bytes) -> list[str] | None:
    """Return per-page layout-preserving Markdown (list index == 0-based page).

    Parses the whole PDF once via pymupdf4llm ``page_chunks=True`` instead of re-parsing the
    document for every page. Returns None on any failure so callers can fall back to the plain
    digital text per page.
    """
    try:
        import pymupdf4llm

        with fitz.open(stream=content, filetype="pdf") as doc:
            chunks = pymupdf4llm.to_markdown(doc, page_chunks=True, show_progress=False)
        return [((c.get("text") if isinstance(c, dict) else "") or "").strip() for c in chunks]
    except Exception as exc:
        logger.warning("pymupdf4llm per-page markdown extraction failed: %s", exc)
        return None


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

    # Layout-preserving Markdown for the digital pages, parsed once for the whole document
    # (per-page indexing) rather than re-parsing the PDF for every page.
    page_md = _pdf_markdown_pages(content)

    parts: list[str] = []
    used_ocr = 0
    for i in range(num_pages):
        ocr_text = ocr_results.get(i, "")
        if i in ocr_pages and ocr_text.strip():
            parts.append(ocr_text)
            used_ocr += 1
        else:
            # Digital (or OCR-failed) page → layout-preserving Markdown, fall back to plain text.
            digital_md = page_md[i] if (page_md is not None and i < len(page_md)) else ""
            parts.append(digital_md or (page_digital[i] or ""))
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


def _iter_header_footer_text(doc) -> list[str]:
    """Collect text from every section header/footer (default, first-page, even-page).

    Headers/footers frequently carry DSGVO-relevant metadata (controller, version/date,
    file reference) that plain paragraph iteration drops. De-duplicated because Word links
    headers across sections by default, so the same text repeats per section.
    """
    parts: list[str] = []
    seen: set[str] = set()
    for section in doc.sections:
        for hf in (
            section.header, section.first_page_header, section.even_page_header,
            section.footer, section.first_page_footer, section.even_page_footer,
        ):
            if hf is None:
                continue
            try:
                for para in hf.paragraphs:
                    txt = (para.text or "").strip()
                    if txt and txt not in seen:
                        seen.add(txt)
                        parts.append(txt)
                for table in hf.tables:
                    md = _docx_table_to_markdown(table)
                    if md and md not in seen:
                        seen.add(md)
                        parts.append(md)
            except Exception as exc:  # malformed header/footer must never break extraction
                logger.debug("DOCX header/footer extraction skipped a part: %s", exc)
    return parts


def _iter_textbox_text(doc) -> list[str]:
    """Collect text inside drawing text boxes (``w:txbxContent``), which ``doc.paragraphs`` skips."""
    parts: list[str] = []
    try:
        for txbx in doc.element.body.iter(qn("w:txbxContent")):
            for p in txbx.iter(qn("w:p")):
                txt = "".join((t.text or "") for t in p.iter(qn("w:t"))).strip()
                if txt:
                    parts.append(txt)
    except Exception as exc:
        logger.debug("DOCX text-box extraction skipped: %s", exc)
    return parts


def _iter_footnote_text(doc) -> list[str]:
    """Collect footnote/endnote text from the related XML parts (skips separator notes)."""
    parts: list[str] = []
    try:
        rels = doc.part.rels.values()
    except Exception:
        return parts
    for rel in rels:
        rtype = getattr(rel, "reltype", "") or ""
        if not (rtype.endswith("/footnotes") or rtype.endswith("/endnotes")):
            continue
        if getattr(rel, "is_external", False):
            continue
        try:
            root = etree.fromstring(rel.target_part.blob)
        except Exception as exc:
            logger.debug("DOCX footnote part unreadable: %s", exc)
            continue
        note_tag = qn("w:footnote") if rtype.endswith("/footnotes") else qn("w:endnote")
        for note in root.iter(note_tag):
            if note.get(qn("w:type")) in ("separator", "continuationSeparator"):
                continue
            txt = "".join((t.text or "") for t in note.iter(qn("w:t"))).strip()
            if txt:
                parts.append(txt)
    return parts


def extract_text_from_docx(content: bytes) -> str:
    """Extract text from DOCX bytes.

    Beyond body paragraphs and tables (rendered as Markdown tables), this also recovers text
    that plain paragraph iteration silently drops: drawing text boxes, section headers/footers
    and footnotes/endnotes — all of which can carry DSGVO-relevant content.
    """
    doc = docx.Document(io.BytesIO(content))
    parts: list[str] = []
    for para in doc.paragraphs:
        if para.text and para.text.strip():
            parts.append(para.text)
    parts.extend(_iter_textbox_text(doc))
    for table in doc.tables:
        md = _docx_table_to_markdown(table)
        if md:
            parts.append(md)
    header_footer = _iter_header_footer_text(doc)
    if header_footer:
        parts.append("--- Kopf-/Fußzeilen ---")
        parts.extend(header_footer)
    footnotes = _iter_footnote_text(doc)
    if footnotes:
        parts.append("--- Fußnoten ---")
        parts.extend(footnotes)
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


def _decode_text_bytes(content: bytes) -> str:
    """Decode arbitrary text bytes: UTF-8 → charset detection → CP1252, with a binary guard.

    Many legacy exports are Latin-1/CP1252 rather than UTF-8; decoding them as UTF-8 fails and
    would otherwise lose the whole document. Content with NUL bytes (the classic binary marker)
    is treated as non-text and yields an empty string.
    """
    try:
        return content.decode("utf-8")
    except UnicodeDecodeError:
        pass
    # NUL bytes → genuinely binary; don't coerce into text.
    if b"\x00" in content[:65536]:
        return ""
    try:
        from charset_normalizer import from_bytes

        best = from_bytes(content).best()
        if best is not None:
            return str(best)
    except Exception:
        pass
    try:
        return content.decode("cp1252")
    except Exception:
        return ""


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
    text = _decode_text_bytes(content)
    if not text:
        logger.debug("No decodable text for %s", filename)
    return ExtractionResult(text=text, extraction_method=EXTRACTION_METHOD_TEXT, char_count=len(text))
