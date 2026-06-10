"""Text extraction from documents (PDF, DOCX, XLSX).

Goals beyond plain text dumping:
- Preserve structure: PDFs are extracted as Markdown (layout/tables) via pymupdf4llm;
  DOCX tables and XLSX sheets are emitted as Markdown tables with column letters, so that
  downstream LLM evidence like "Sheet X, Spalte C, Zeile 12" stays meaningful.
- Mixed scanned PDFs: decide per page whether to OCR (vision LLM via the OpenAI-compatible
  chat-completions API — works against Ollama, vLLM and llama.cpp), OCR'ing only the sparse
  pages, in parallel.
- Quality signals: report char/page counts and the OCR page ratio so weak extractions can
  be flagged downstream.
"""
import base64
import io
import logging
import re
import shutil
import subprocess
import tempfile
import time
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
        ocr_low_quality_pages: Number of pages that were OCR'd but still recovered almost no text
            (below ``ocr_min_chars_per_page``) — i.e. likely lost despite OCR. A downstream quality
            signal so reviewers can spot scans that did not extract cleanly.
    """
    text: str
    extraction_method: Literal["text", "ocr"]
    char_count: int = 0
    page_count: int = 0
    ocr_page_ratio: float = 0.0
    ocr_low_quality_pages: int = 0


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


def _ocr_chat_endpoint() -> tuple[str, dict[str, str]]:
    """Resolve the OpenAI-compatible chat-completions URL and auth headers for OCR.

    Resolution order for the base URL: explicit ``ocr_base_url`` override → the custom server
    when ``llm_provider=openai_compatible`` → the Ollama server (default). A missing ``/v1``
    suffix is appended. The API key follows the same fallback (``ocr_api_key`` → ``llm_api_key``
    for openai_compatible → none for Ollama).
    """
    base = (getattr(settings, "ocr_base_url", "") or "").strip()
    api_key = settings.ocr_api_key.get_secret_value() if hasattr(settings, "ocr_api_key") else ""
    if not base:
        if settings.llm_provider.lower() == "openai_compatible" and (settings.llm_base_url or "").strip():
            base = settings.llm_base_url
            api_key = api_key or settings.llm_api_key.get_secret_value()
        else:
            base = settings.ollama_base_url or ""
    base = base.rstrip("/")
    if not base.endswith("/v1"):
        base = f"{base}/v1"
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    return f"{base}/chat/completions", headers


def _ocr_model_name() -> str:
    """OCR vision model: explicit ``ocr_model`` override, else the legacy ``ollama_ocr_model``."""
    return (getattr(settings, "ocr_model", "") or "").strip() or settings.ollama_ocr_model


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
    """OCR the given PDF pages concurrently via a vision LLM. Returns {page_index: text}.

    Uses the OpenAI-compatible chat-completions API (image as base64 data URI), so the vision
    backend can be Ollama (default), vLLM or llama.cpp — see :func:`_ocr_chat_endpoint`.

    Each page is retried up to ``ocr_retry_attempts`` times on a transient error or a near-empty
    response (with a short backoff) instead of silently losing the page on the first hiccup. The
    retry render DPI is escalated from ``ocr_dpi`` toward ``ocr_max_dpi`` across attempts, so an
    under-resolved scan gets a sharper image rather than the same blurry one again. The most
    complete recovery across attempts is kept (best-effort). OCR runs at temperature 0 for
    reproducible output.
    """
    chat_url, headers = _ocr_chat_endpoint()
    model = _ocr_model_name()
    timeout = httpx.Timeout(settings.ollama_timeout_seconds, connect=10.0)
    base_dpi = getattr(settings, "ocr_dpi", 300)
    max_dpi = max(base_dpi, getattr(settings, "ocr_max_dpi", 400))
    min_chars = getattr(settings, "ocr_min_chars_per_page", 50)
    concurrency = max(1, getattr(settings, "ocr_concurrency", 4))
    attempts = max(1, getattr(settings, "ocr_retry_attempts", 2))

    def _dpi_for_attempt(attempt: int) -> int:
        """Configured DPI on the first attempt; linearly escalate toward max_dpi on later ones."""
        if attempts <= 1 or base_dpi >= max_dpi:
            return base_dpi
        step = (max_dpi - base_dpi) / (attempts - 1)
        return int(round(base_dpi + step * (attempt - 1)))

    def _ocr_one(i: int) -> tuple[int, str]:
        best = ""
        for attempt in range(1, attempts + 1):
            dpi = _dpi_for_attempt(attempt)
            try:
                png_bytes = _pdf_page_to_png_bytes(content, i, dpi=dpi)
                image_uri = f"data:image/png;base64,{base64.b64encode(png_bytes).decode()}"
                payload = {
                    "model": model,
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": OCR_PROMPT},
                                {"type": "image_url", "image_url": {"url": image_uri}},
                            ],
                        }
                    ],
                    "stream": False,
                    "temperature": 0,
                }
                resp = httpx.post(chat_url, json=payload, headers=headers, timeout=timeout)
                resp.raise_for_status()
                data = resp.json()
                choices = data.get("choices") or []
                message = (choices[0].get("message") or {}) if choices else {}
                text = (message.get("content") or "").strip()
                if len(text) > len(best):
                    best = text  # keep the most complete recovery across attempts
                if len(text.strip()) >= min_chars:
                    return i, text
                logger.warning(
                    "Vision OCR recovered little text for page %s at %d DPI (attempt %d/%d)",
                    i + 1, dpi, attempt, attempts,
                )
            except Exception as exc:
                logger.warning("Vision OCR failed for page %s (attempt %d/%d): %s", i + 1, attempt, attempts, exc)
            if attempt < attempts:
                time.sleep(attempt)  # simple linear backoff: 1s, 2s, ...
        return i, best

    results: dict[int, str] = {}
    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        for i, text in pool.map(_ocr_one, page_indices):
            results[i] = text
    return results


def _image_heavy_pages(doc) -> set[int]:
    """Return indices of pages dominated by a scanned image but carrying little digital text.

    Such pages are not "sparse" by character count (a running header/footer often supplies enough
    text to clear ``ocr_min_chars_per_page``), yet their body is an image whose content would be
    lost without OCR. A page qualifies when an embedded image covers at least
    ``ocr_image_area_threshold`` of the page area while the digital text stays below
    ``ocr_image_heavy_max_chars``. Returns an empty set when the heuristic is disabled
    (threshold >= 1.0).
    """
    area_threshold = getattr(settings, "ocr_image_area_threshold", 0.5)
    max_chars = getattr(settings, "ocr_image_heavy_max_chars", 300)
    if area_threshold >= 1.0:
        return set()
    flagged: set[int] = set()
    for i in range(len(doc)):
        page = doc[i]
        if len((page.get_text() or "").strip()) >= max_chars:
            continue
        page_area = abs(page.rect.width * page.rect.height)
        if page_area <= 0:
            continue
        try:
            infos = page.get_image_info()
        except Exception as exc:  # never let image probing break extraction
            logger.debug("Image-info probe failed on page %s: %s", i + 1, exc)
            continue
        max_frac = 0.0
        for info in infos:
            bbox = info.get("bbox")
            if not bbox:
                continue
            w = max(0.0, bbox[2] - bbox[0])
            h = max(0.0, bbox[3] - bbox[1])
            max_frac = max(max_frac, (w * h) / page_area)
        if max_frac >= area_threshold:
            flagged.add(i)
    return flagged


# Stop-word sets for the lightweight DE/EN language heuristic (deliberately non-overlapping so the
# two languages give a clean signal). Not a full language identifier — just enough to pick the LLM
# language hint when the caller did not specify one.
_DE_STOPWORDS = frozenset(
    {"der", "die", "das", "und", "ist", "nicht", "werden", "wird", "für", "mit", "auch",
     "sich", "eine", "einer", "von", "den", "dem", "des", "im", "zur", "zum", "bei", "durch"}
)
_EN_STOPWORDS = frozenset(
    {"the", "and", "are", "with", "for", "this", "that", "from", "have", "will", "not",
     "shall", "been", "their", "which", "such", "any", "into", "data", "processing"}
)


def detect_language(text: str | None) -> str | None:
    """Best-effort DE/EN detection via stop-word frequency. Returns "de", "en", or None.

    Lightweight (no extra dependency); used to set the LLM language hint when the caller did not
    specify a language. Returns None when the text is too short or the signal too weak to decide.
    """
    if not text:
        return None
    words = re.findall(r"[a-zäöüß]+", text.lower())
    if len(words) < 20:
        return None
    de = sum(1 for w in words if w in _DE_STOPWORDS)
    en = sum(1 for w in words if w in _EN_STOPWORDS)
    if de == 0 and en == 0:
        return None
    if de >= en * 1.2:
        return "de"
    if en >= de * 1.2:
        return "en"
    return None


def extract_text_from_pdf(content: bytes) -> ExtractionResult:
    """
    Extract text from PDF as Markdown.

    Uses PyMuPDF to detect sparse (likely scanned) pages. When OCR is enabled, only the
    sparse pages are OCR'd via the vision LLM (per-page, in parallel) and merged with the
    digital pages; fully digital PDFs skip OCR entirely.
    """
    with fitz.open(stream=content, filetype="pdf") as doc:
        # Password-protected/encrypted PDFs yield empty text silently — surface a clear error
        # instead so the upload is flagged rather than stored as an empty extraction.
        if doc.needs_pass:
            raise UnsupportedDocumentError(
                "Die PDF ist passwortgeschützt/verschlüsselt und kann nicht ausgelesen werden. "
                "Bitte ein entsperrtes PDF hochladen."
            )
        num_pages = len(doc)
        page_digital = [doc[i].get_text() for i in range(num_pages)]
        # Pages that are mostly a scanned image but carry a little digital text are not "sparse"
        # by char count, yet need OCR — detect them while the document is open.
        image_heavy = _image_heavy_pages(doc) if settings.ollama_ocr_enabled else set()

    if num_pages == 0:
        return ExtractionResult(text="", extraction_method=EXTRACTION_METHOD_TEXT)

    min_chars = settings.ocr_min_chars_per_page
    sparse_pages = sorted(
        {i for i, t in enumerate(page_digital) if len((t or "").strip()) < min_chars} | image_heavy
    )

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
    low_quality = 0
    for i in range(num_pages):
        ocr_text = ocr_results.get(i, "")
        if i in ocr_pages and ocr_text.strip():
            parts.append(ocr_text)
            used_ocr += 1
            page_text = ocr_text
        else:
            # Digital (or OCR-failed) page → layout-preserving Markdown, fall back to plain text.
            digital_md = page_md[i] if (page_md is not None and i < len(page_md)) else ""
            page_text = digital_md or (page_digital[i] or "")
            parts.append(page_text)
        # A page we intended to OCR that still has almost no text was likely lost despite OCR.
        if i in ocr_pages and len(page_text.strip()) < min_chars:
            low_quality += 1
    text = "\n\n".join(p for p in parts if p)
    method = EXTRACTION_METHOD_OCR if used_ocr > 0 else EXTRACTION_METHOD_TEXT
    if low_quality:
        logger.warning(
            "OCR recovered little/no text on %d of %d page(s) — extraction may be incomplete",
            low_quality, num_pages,
        )
    return ExtractionResult(
        text=text,
        extraction_method=method,
        char_count=len(text),
        page_count=num_pages,
        ocr_page_ratio=(used_ocr / num_pages) if num_pages else 0.0,
        ocr_low_quality_pages=low_quality,
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


# Map a file extension to the PyMuPDF image filetype it understands.
_IMAGE_EXT_TO_FITZ = {"jpg": "jpg", "jpeg": "jpg", "png": "png", "tif": "tiff", "tiff": "tiff"}


def extract_text_from_image(content: bytes, filetype: str) -> ExtractionResult:
    """Extract text from a standalone scanned image (JPG/PNG/TIFF) via the PDF/OCR path.

    The image is converted to a (possibly multi-page, for TIFF) PDF with PyMuPDF and run through
    :func:`extract_text_from_pdf`, so it reuses the whole per-page vision-OCR pipeline
    (retries, quality signal, ocr_page_ratio). An image has no digital text layer, so every page
    is sparse → OCR. With OCR disabled the result is empty text (a warning is logged), consistent
    with how fully scanned PDFs behave today.
    """
    try:
        with fitz.open(stream=content, filetype=filetype) as img_doc:
            pdf_bytes = img_doc.convert_to_pdf()
    except Exception:
        logger.exception("Image→PDF conversion failed", extra={"filetype": filetype})
        return ExtractionResult(text="", extraction_method=EXTRACTION_METHOD_OCR)
    if not settings.ollama_ocr_enabled:
        logger.warning("Image upload but OCR is disabled — returning empty text (filetype=%s)", filetype)
    return extract_text_from_pdf(pdf_bytes)


def extract_text(filename: str, content: bytes) -> ExtractionResult:
    """
    Dispatcher for text extraction. Returns ExtractionResult with text and
    extraction_method ("text" or "ocr" for PDFs/images that used vision OCR).
    """
    filename_lower = filename.lower()
    if filename_lower.endswith(".pdf"):
        return extract_text_from_pdf(content)
    ext = filename_lower.rsplit(".", 1)[-1] if "." in filename_lower else ""
    if ext in _IMAGE_EXT_TO_FITZ:
        try:
            return extract_text_from_image(content, _IMAGE_EXT_TO_FITZ[ext])
        except Exception:
            logger.exception("Image text extraction failed", extra={"filename": filename})
            raise
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
