"""PDF and image text extraction with per-page Markdown and OCR support.

Also exports the shared anchor/assemble utilities used by the PPTX extractor
in document_processor (imported from there to avoid circular dependencies).
"""

import logging
from dataclasses import dataclass
from typing import Literal

import fitz  # PyMuPDF

from app.config import settings
from app.services.ocr_service import _ocr_pages

logger = logging.getLogger(__name__)

EXTRACTION_METHOD_TEXT: Literal["text"] = "text"
EXTRACTION_METHOD_OCR: Literal["ocr"] = "ocr"


class UnsupportedDocumentError(ValueError):
    """Raised when a document format cannot be extracted."""


@dataclass
class ExtractionResult:
    """Result of text extraction.

    Args:
        text: Extracted text (Markdown for PDF/DOCX/XLSX).
        extraction_method: "text" (digital) or "ocr" (at least one page via vision OCR).
        char_count: Length of the extracted text (quality signal).
        page_count: Number of pages (PDF) or 0 for non-paged formats.
        ocr_page_ratio: Fraction of pages extracted via OCR (0.0 = fully digital).
        ocr_low_quality_pages: Pages OCR'd but still yielding almost no text.
    """

    text: str
    extraction_method: Literal["text", "ocr"]
    char_count: int = 0
    page_count: int = 0
    ocr_page_ratio: float = 0.0
    ocr_low_quality_pages: int = 0


# ---------------------------------------------------------------------------
# Shared anchor/assemble utilities (also used by PPTX extractor)
# ---------------------------------------------------------------------------


def _page_anchor(page_index: int) -> str:
    """Anchor line marking the start of a PDF page in the extracted text (1-based)."""
    return f"[Seite {page_index + 1}]"


def _assemble_anchored(parts: list[str], total: int, anchor_fn) -> str:
    """Join per-unit texts (pages/slides), prefixing each non-empty unit with its anchor.

    Single-unit documents are returned without an anchor.
    """
    non_empty = [(i, p) for i, p in enumerate(parts) if p and p.strip()]
    if total <= 1:
        return "\n\n".join(p for _i, p in non_empty)
    return "\n\n".join(f"{anchor_fn(i)}\n{p}" for i, p in non_empty)


def _assemble_pages(pages: list[str], num_pages: int) -> str:
    """Join per-page texts with "[Seite N]" anchors."""
    return _assemble_anchored(pages, num_pages, _page_anchor)


# ---------------------------------------------------------------------------
# PDF extraction helpers
# ---------------------------------------------------------------------------


def _pdf_markdown(content: bytes, pages: list[int] | None = None) -> str:
    """Extract layout-/table-preserving Markdown from a PDF via pymupdf4llm."""
    try:
        import pymupdf4llm

        with fitz.open(stream=content, filetype="pdf") as doc:
            return pymupdf4llm.to_markdown(
                doc, pages=pages, show_progress=False
            ).strip()
    except Exception as exc:
        logger.warning(
            "pymupdf4llm markdown extraction failed, falling back to get_text: %s", exc
        )
        try:
            with fitz.open(stream=content, filetype="pdf") as doc:
                indices = pages if pages is not None else range(len(doc))
                return "\n".join(doc[i].get_text() for i in indices).strip()
        except Exception as exc2:
            logger.warning("PyMuPDF get_text fallback also failed: %s", exc2)
            return ""


def _pdf_markdown_pages(content: bytes) -> list[str] | None:
    """Return per-page layout-preserving Markdown. Returns None on failure."""
    try:
        import pymupdf4llm

        with fitz.open(stream=content, filetype="pdf") as doc:
            chunks = pymupdf4llm.to_markdown(doc, page_chunks=True, show_progress=False)
        return [
            ((c.get("text") if isinstance(c, dict) else "") or "").strip()
            for c in chunks
        ]
    except Exception as exc:
        logger.warning("pymupdf4llm per-page markdown extraction failed: %s", exc)
        return None


def _image_heavy_pages(doc) -> set[int]:
    """Return indices of pages dominated by a scanned image but carrying little digital text."""
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
        except Exception as exc:
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


def _digital_pdf_result(
    content: bytes, page_digital: list[str], num_pages: int
) -> ExtractionResult:
    """Assemble the fully digital extraction: per-page Markdown with page anchors."""
    page_md = _pdf_markdown_pages(content)
    if page_md is not None:
        pages = [
            ((page_md[i] if i < len(page_md) else "") or (page_digital[i] or ""))
            for i in range(num_pages)
        ]
        text = _assemble_pages(pages, num_pages)
    else:
        text = _pdf_markdown(content) or _assemble_pages(page_digital, num_pages)
    return ExtractionResult(
        text=text,
        extraction_method=EXTRACTION_METHOD_TEXT,
        char_count=len(text),
        page_count=num_pages,
        ocr_page_ratio=0.0,
    )


# ---------------------------------------------------------------------------
# Public extraction functions
# ---------------------------------------------------------------------------


def extract_text_from_pdf(content: bytes) -> ExtractionResult:
    """Extract text from PDF as Markdown with per-page anchors.

    Uses PyMuPDF to detect sparse (likely scanned) pages. When OCR is enabled,
    only the sparse pages are OCR'd via the vision LLM and merged with digital pages.
    """
    with fitz.open(stream=content, filetype="pdf") as doc:
        if doc.needs_pass:
            raise UnsupportedDocumentError(
                "Die PDF ist passwortgeschützt/verschlüsselt und kann nicht ausgelesen werden. "
                "Bitte ein entsperrtes PDF hochladen."
            )
        num_pages = len(doc)
        page_digital = [doc[i].get_text() for i in range(num_pages)]
        image_heavy = _image_heavy_pages(doc) if settings.ollama_ocr_enabled else set()

    if num_pages == 0:
        return ExtractionResult(text="", extraction_method=EXTRACTION_METHOD_TEXT)

    min_chars = settings.ocr_min_chars_per_page
    sparse_pages = sorted(
        {i for i, t in enumerate(page_digital) if len((t or "").strip()) < min_chars}
        | image_heavy
    )

    if not settings.ollama_ocr_enabled or not sparse_pages:
        return _digital_pdf_result(content, page_digital, num_pages)

    if getattr(settings, "ocr_per_page", True):
        ocr_pages = set(sparse_pages)
    else:
        avg = sum(len((t or "").strip()) for t in page_digital) / num_pages
        ocr_pages = set(range(num_pages)) if avg < min_chars else set()

    if not ocr_pages:
        return _digital_pdf_result(content, page_digital, num_pages)

    max_ocr_pages = getattr(settings, "ocr_max_pages", 200)
    ocr_targets = sorted(ocr_pages)[:max_ocr_pages]
    if len(ocr_pages) > max_ocr_pages:
        logger.warning(
            "OCR limited to first %d of %d candidate pages",
            max_ocr_pages,
            len(ocr_pages),
        )
    ocr_results = _ocr_pages(content, ocr_targets)

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
            digital_md = (
                page_md[i] if (page_md is not None and i < len(page_md)) else ""
            )
            page_text = digital_md or (page_digital[i] or "")
            parts.append(page_text)
        if i in ocr_pages and len(page_text.strip()) < min_chars:
            low_quality += 1
    text = _assemble_pages(parts, num_pages)
    method = EXTRACTION_METHOD_OCR if used_ocr > 0 else EXTRACTION_METHOD_TEXT
    if low_quality:
        logger.warning(
            "OCR recovered little/no text on %d of %d page(s) — extraction may be incomplete",
            low_quality,
            num_pages,
        )
    return ExtractionResult(
        text=text,
        extraction_method=method,
        char_count=len(text),
        page_count=num_pages,
        ocr_page_ratio=(used_ocr / num_pages) if num_pages else 0.0,
        ocr_low_quality_pages=low_quality,
    )


def extract_text_from_image(content: bytes, filetype: str) -> ExtractionResult:
    """Extract text from a standalone scanned image (JPG/PNG/TIFF) via the PDF/OCR path.

    The image is converted to a PDF with PyMuPDF and run through extract_text_from_pdf,
    reusing the whole per-page vision-OCR pipeline.
    """
    try:
        with fitz.open(stream=content, filetype=filetype) as img_doc:
            pdf_bytes = img_doc.convert_to_pdf()
    except Exception:
        logger.exception("Image→PDF conversion failed", extra={"filetype": filetype})
        return ExtractionResult(text="", extraction_method=EXTRACTION_METHOD_OCR)
    if not settings.ollama_ocr_enabled:
        logger.warning(
            "Image upload but OCR is disabled — returning empty text (filetype=%s)",
            filetype,
        )
    return extract_text_from_pdf(pdf_bytes)
