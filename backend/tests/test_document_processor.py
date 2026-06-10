"""Unit tests for document text extraction logic (no DB, no external services)."""
import io

import pytest

import app.services.document_processor as dp
from app.services.document_processor import (
    extract_text_from_docx,
    extract_text_from_xlsx,
    extract_text,
    ExtractionResult,
    EXTRACTION_METHOD_TEXT,
)


def _make_docx_bytes(paragraphs: list[str], table_rows: list[list[str]] | None = None) -> bytes:
    """Build a minimal in-memory DOCX file."""
    import docx as python_docx

    doc = python_docx.Document()
    for para in paragraphs:
        doc.add_paragraph(para)
    if table_rows:
        table = doc.add_table(rows=len(table_rows), cols=len(table_rows[0]))
        for r_idx, row in enumerate(table_rows):
            for c_idx, cell_text in enumerate(row):
                table.rows[r_idx].cells[c_idx].text = cell_text
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def _make_docx_with_header_footer(body: str, header: str, footer: str) -> bytes:
    """Build a DOCX whose header/footer carry text the body does not."""
    import docx as python_docx

    doc = python_docx.Document()
    doc.add_paragraph(body)
    section = doc.sections[0]
    section.header.paragraphs[0].text = header
    section.footer.paragraphs[0].text = footer
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def _make_xlsx_bytes(sheets: dict[str, list[list]]) -> bytes:
    """Build a minimal in-memory XLSX file."""
    import openpyxl

    wb = openpyxl.Workbook()
    first = True
    for sheet_name, rows in sheets.items():
        if first:
            ws = wb.active
            ws.title = sheet_name
            first = False
        else:
            ws = wb.create_sheet(sheet_name)
        for row in rows:
            ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


class TestExtractTextFromDocx:
    def test_paragraphs_extracted(self):
        content = _make_docx_bytes(["Erster Absatz", "Zweiter Absatz"])
        text = extract_text_from_docx(content)
        assert "Erster Absatz" in text
        assert "Zweiter Absatz" in text

    def test_table_cells_extracted(self):
        content = _make_docx_bytes([], table_rows=[["Name", "Wert"], ["Alice", "42"]])
        text = extract_text_from_docx(content)
        assert "Name" in text
        assert "Alice" in text

    def test_empty_document(self):
        content = _make_docx_bytes([])
        text = extract_text_from_docx(content)
        assert isinstance(text, str)

    def test_returns_string(self):
        content = _make_docx_bytes(["Hello"])
        result = extract_text_from_docx(content)
        assert isinstance(result, str)


class TestDocxHeaderFooter:
    def test_header_and_footer_text_recovered(self):
        # Header/footer often carry the controller, version/date or file reference, which plain
        # paragraph iteration drops. They must survive extraction.
        content = _make_docx_with_header_footer(
            body="Verarbeitungstätigkeit Lohnabrechnung",
            header="Verantwortlicher: Muster GmbH",
            footer="Stand: 01.01.2026 — Az. DS-2026-042",
        )
        text = extract_text_from_docx(content)
        assert "Verarbeitungstätigkeit Lohnabrechnung" in text
        assert "Verantwortlicher: Muster GmbH" in text
        assert "Az. DS-2026-042" in text


class TestExtractTextFromXlsx:
    def test_single_sheet_data(self):
        content = _make_xlsx_bytes({"Sheet1": [["Datum", "Betrag"], ["2024-01-01", 100]]})
        text = extract_text_from_xlsx(content)
        assert "Datum" in text
        assert "2024-01-01" in text

    def test_multiple_sheets(self):
        content = _make_xlsx_bytes({
            "Blatt1": [["A", "B"]],
            "Blatt2": [["C", "D"]],
        })
        text = extract_text_from_xlsx(content)
        assert "Blatt1" in text
        assert "Blatt2" in text
        assert "A" in text
        assert "C" in text

    def test_empty_sheet(self):
        content = _make_xlsx_bytes({"Empty": []})
        text = extract_text_from_xlsx(content)
        assert isinstance(text, str)


class TestExtractTextDispatcher:
    def test_docx_dispatch(self):
        content = _make_docx_bytes(["Testinhalt"])
        result = extract_text("file.docx", content)
        assert isinstance(result, ExtractionResult)
        assert result.extraction_method == EXTRACTION_METHOD_TEXT
        assert "Testinhalt" in result.text

    def test_xlsx_dispatch(self):
        content = _make_xlsx_bytes({"S1": [["Zelle"]]})
        result = extract_text("report.xlsx", content)
        assert isinstance(result, ExtractionResult)
        assert result.extraction_method == EXTRACTION_METHOD_TEXT
        assert "Zelle" in result.text

    def test_plain_text_fallback(self):
        content = "Hallo Welt".encode("utf-8")
        result = extract_text("readme.txt", content)
        assert isinstance(result, ExtractionResult)
        assert "Hallo Welt" in result.text

    def test_binary_fallback_returns_empty(self):
        content = b"\xff\xfe\x00\x01"  # not valid UTF-8
        result = extract_text("unknown.bin", content)
        assert isinstance(result, ExtractionResult)
        assert result.text == ""

    def test_cp1252_text_is_decoded_not_lost(self):
        # Legacy exports are often CP1252/Latin-1; decoding as UTF-8 fails. Such text must not be
        # silently dropped (no NUL bytes → it is real text, not binary).
        content = "Müller Straße – Zweck: Personalverwaltung".encode("cp1252")
        result = extract_text("export.txt", content)
        assert result.text != ""
        assert "ller" in result.text and "Personalverwaltung" in result.text

    def test_docx_uppercase_extension(self):
        content = _make_docx_bytes(["Groß"])
        result = extract_text("DOC.DOCX", content)
        assert "Groß" in result.text


class TestStructurePreservation:
    def test_xlsx_preserves_columns_with_empty_cells(self):
        # Middle column empty: column alignment (and column letters) must stay intact so that
        # evidence like "Spalte C" remains meaningful.
        content = _make_xlsx_bytes({"VVT": [["Zweck", None, "Rechtsgrundlage"], ["Lohn", None, "Art. 6"]]})
        text = extract_text_from_xlsx(content)
        # Column-letter header row present
        assert "| A | B | C |" in text
        # Row keeps the empty middle column → 'Zweck' in A, '' in B, 'Rechtsgrundlage' in C
        assert "| Zweck |  | Rechtsgrundlage |" in text
        assert "| Lohn |  | Art. 6 |" in text

    def test_docx_table_rendered_as_markdown(self):
        content = _make_docx_bytes([], table_rows=[["Feld", "Wert"], ["Zweck", "Lohnabrechnung"]])
        text = extract_text_from_docx(content)
        assert "| Feld | Wert |" in text
        assert "| --- | --- |" in text
        assert "| Zweck | Lohnabrechnung |" in text


class TestLegacyDoc:
    def test_doc_without_converter_raises(self, monkeypatch):
        import app.services.document_processor as dp

        # Simulate no converter installed → clear error instead of silent empty text.
        monkeypatch.setattr(dp.shutil, "which", lambda _name: None)
        with pytest.raises(dp.UnsupportedDocumentError):
            extract_text("altes_dokument.doc", b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1fakeole2")


class _FakeResp:
    def __init__(self, content: str):
        self._content = content

    def raise_for_status(self):
        return None

    def json(self):
        return {"message": {"content": self._content}}


class TestOcrRetry:
    """A3: per-page OCR is retried on transient failure / empty output instead of silently lost."""

    def _patch_render_and_sleep(self, monkeypatch):
        monkeypatch.setattr(dp, "_pdf_page_to_png_bytes", lambda content, i, dpi=150: b"x")
        monkeypatch.setattr(dp.time, "sleep", lambda _s: None)

    def test_retries_until_attempts_exhausted_then_empty(self, monkeypatch):
        self._patch_render_and_sleep(monkeypatch)
        monkeypatch.setattr(dp.settings, "ocr_retry_attempts", 3, raising=False)
        calls = {"n": 0}

        def _always_fail(*a, **k):
            calls["n"] += 1
            raise RuntimeError("boom")

        monkeypatch.setattr(dp.httpx, "post", _always_fail)
        result = dp._ocr_pages(b"fakepdf", [0])
        assert result == {0: ""}
        assert calls["n"] == 3  # one attempt per configured retry

    def test_succeeds_after_a_transient_failure(self, monkeypatch):
        self._patch_render_and_sleep(monkeypatch)
        monkeypatch.setattr(dp.settings, "ocr_retry_attempts", 2, raising=False)
        calls = {"n": 0}

        def _fail_then_ok(*a, **k):
            calls["n"] += 1
            if calls["n"] == 1:
                raise RuntimeError("transient")
            return _FakeResp("Seiteninhalt erkannt")

        monkeypatch.setattr(dp.httpx, "post", _fail_then_ok)
        result = dp._ocr_pages(b"fakepdf", [0])
        assert result == {0: "Seiteninhalt erkannt"}
        assert calls["n"] == 2

    def test_empty_response_is_retried(self, monkeypatch):
        self._patch_render_and_sleep(monkeypatch)
        monkeypatch.setattr(dp.settings, "ocr_retry_attempts", 2, raising=False)
        calls = {"n": 0}

        def _empty_then_ok(*a, **k):
            calls["n"] += 1
            return _FakeResp("" if calls["n"] == 1 else "Treffer")

        monkeypatch.setattr(dp.httpx, "post", _empty_then_ok)
        result = dp._ocr_pages(b"fakepdf", [0])
        assert result == {0: "Treffer"}
        assert calls["n"] == 2


class TestOcrQualitySignal:
    def test_digital_formats_report_zero_low_quality_pages(self):
        # Non-paged / digital extraction carries the default 0 (no OCR pages, nothing lost).
        result = extract_text("report.docx", _make_docx_bytes(["Inhalt"]))
        assert result.ocr_low_quality_pages == 0


def _make_png_bytes() -> bytes:
    """Build a tiny in-memory PNG via PyMuPDF (no Pillow dependency)."""
    import fitz

    pix = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 12, 12), False)
    pix.clear_with(255)
    return pix.tobytes("png")


class TestImageUpload:
    """A4: standalone scanned images route through the PDF/OCR path."""

    def test_png_routes_through_pdf_path_without_crashing(self, monkeypatch):
        # OCR disabled → empty text, but conversion + routing must succeed (no exception).
        monkeypatch.setattr(dp.settings, "ollama_ocr_enabled", False, raising=False)
        result = extract_text("scan.png", _make_png_bytes())
        assert isinstance(result, ExtractionResult)
        assert isinstance(result.text, str)

    def test_unknown_image_bytes_do_not_raise(self, monkeypatch):
        monkeypatch.setattr(dp.settings, "ollama_ocr_enabled", False, raising=False)
        result = extract_text("scan.png", b"not a real image")
        assert isinstance(result, ExtractionResult)


def _make_encrypted_pdf_bytes() -> bytes:
    """Build a password-protected (AES-256) PDF that requires a user password to read."""
    import fitz

    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Vertraulicher Inhalt")
    out = doc.tobytes(
        encryption=fitz.PDF_ENCRYPT_AES_256,
        user_pw="secret",
        owner_pw="owner",
    )
    doc.close()
    return out


def _make_image_heavy_pdf_bytes() -> bytes:
    """Build a PDF page that is mostly a scanned-style image with only a tiny header text."""
    import fitz

    doc = fitz.open()
    page = doc.new_page()
    pix = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 400, 520), False)
    pix.clear_with(220)
    page.insert_image(page.rect, pixmap=pix)
    page.insert_text((72, 18), "Kopfzeile Az. DS-1")  # short digital text → not 'sparse' by chars
    out = doc.tobytes()
    doc.close()
    return out


class TestEncryptedPdf:
    """A3: password-protected PDFs raise a clear error instead of yielding empty text."""

    def test_encrypted_pdf_raises(self):
        with pytest.raises(dp.UnsupportedDocumentError):
            dp.extract_text_from_pdf(_make_encrypted_pdf_bytes())


class TestImageHeavyPages:
    """A2: pages dominated by an image but with a little digital text are OCR candidates."""

    def test_image_heavy_page_detected(self):
        import fitz

        with fitz.open(stream=_make_image_heavy_pdf_bytes(), filetype="pdf") as doc:
            assert dp._image_heavy_pages(doc) == {0}

    def test_text_page_not_flagged(self):
        import fitz

        doc = fitz.open()
        page = doc.new_page()
        page.insert_text((72, 72), "Ausführlicher Fließtext " * 40)  # plenty of digital text
        data = doc.tobytes()
        doc.close()
        with fitz.open(stream=data, filetype="pdf") as reopened:
            assert dp._image_heavy_pages(reopened) == set()

    def test_disabled_via_threshold(self, monkeypatch):
        import fitz

        monkeypatch.setattr(dp.settings, "ocr_image_area_threshold", 1.0, raising=False)
        with fitz.open(stream=_make_image_heavy_pdf_bytes(), filetype="pdf") as doc:
            assert dp._image_heavy_pages(doc) == set()


class TestDetectLanguage:
    """A4: lightweight DE/EN language detection for the LLM language hint."""

    def test_german_text(self):
        text = (
            "Die Verarbeitung der personenbezogenen Daten erfolgt zur Lohnabrechnung und wird "
            "auf Grundlage der gesetzlichen Vorgaben durchgeführt, damit die Fristen eingehalten werden."
        )
        assert dp.detect_language(text) == "de"

    def test_english_text(self):
        text = (
            "The processing of the personal data is carried out for payroll purposes and shall "
            "be based on the legal requirements so that the retention periods are not exceeded."
        )
        assert dp.detect_language(text) == "en"

    def test_too_short_returns_none(self):
        assert dp.detect_language("Lohn") is None
        assert dp.detect_language("") is None
        assert dp.detect_language(None) is None


class TestImageMagicBytes:
    """A4: magic-byte validation accepts real image headers and rejects mismatches."""

    def _verify(self):
        from app.api.routes.documents import _verify_magic_bytes
        return _verify_magic_bytes

    def test_accepts_matching_image_headers(self):
        from fastapi import HTTPException

        verify = self._verify()
        verify(b"\xff\xd8\xff\xe0\x00\x10JFIF", "jpg", "s.jpg")
        verify(b"\x89PNG\r\n\x1a\n\x00\x00", "png", "s.png")
        verify(b"II*\x00\x08\x00\x00\x00", "tiff", "s.tiff")
        verify(b"MM\x00*\x00\x00\x00\x08", "tiff", "s.tiff")

    def test_rejects_mismatched_header(self):
        from fastapi import HTTPException

        verify = self._verify()
        with pytest.raises(HTTPException) as exc:
            verify(b"%PDF-1.7 ...", "png", "fake.png")
        assert exc.value.status_code == 415
