"""Unit tests for document text extraction logic (no DB, no external services)."""
import io

import pytest

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
