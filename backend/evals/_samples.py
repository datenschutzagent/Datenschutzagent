"""In-memory gold sample documents + expectations for the extraction evals.

Documents are generated programmatically (no binary fixtures in the repo) so the gold set is
transparent and diffable. Each sample declares the tokens that must survive extraction and,
for tabular formats, a column-header signature that must be preserved.
"""
from __future__ import annotations

import io
from dataclasses import dataclass, field


@dataclass(frozen=True)
class ExtractionSample:
    key: str
    filename: str
    builder: "callable"          # () -> bytes
    expected_tokens: list[str]   # must all appear in the extracted text
    column_header: str | None = None  # e.g. "| A | B | C |" for tabular formats
    min_chars: int = 1


def _vvt_xlsx_bytes() -> bytes:
    """A small VVT/ROPA sheet with an intentionally empty middle column."""
    import openpyxl

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "VVT"
    rows = [
        ["Verarbeitungstätigkeit", None, "Rechtsgrundlage", "Speicherdauer"],
        ["Lohnabrechnung", None, "Art. 6 Abs. 1 lit. c DSGVO", "10 Jahre"],
        ["Bewerbermanagement", None, "Art. 6 Abs. 1 lit. b DSGVO", "6 Monate"],
    ]
    for r in rows:
        ws.append(r)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _avv_docx_bytes() -> bytes:
    """A small AVV-style DOCX containing a paragraph and a table."""
    import docx

    doc = docx.Document()
    doc.add_paragraph("Auftragsverarbeitungsvertrag gemäß Art. 28 DSGVO")
    doc.add_paragraph("Der Auftragsverarbeiter verarbeitet personenbezogene Daten weisungsgebunden.")
    table = doc.add_table(rows=3, cols=2)
    cells = [["Gegenstand", "Lohnbuchhaltung"], ["Subunternehmer", "Keine"], ["Drittland", "Nein"]]
    for r_idx, row in enumerate(cells):
        for c_idx, val in enumerate(row):
            table.rows[r_idx].cells[c_idx].text = val
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


SAMPLES: dict[str, ExtractionSample] = {
    "vvt_xlsx": ExtractionSample(
        key="vvt_xlsx",
        filename="vvt.xlsx",
        builder=_vvt_xlsx_bytes,
        expected_tokens=["Lohnabrechnung", "Art. 6 Abs. 1 lit. c DSGVO", "10 Jahre", "Bewerbermanagement"],
        column_header="| A | B | C | D |",
        min_chars=60,
    ),
    "avv_docx": ExtractionSample(
        key="avv_docx",
        filename="avv.docx",
        builder=_avv_docx_bytes,
        expected_tokens=["Art. 28 DSGVO", "Gegenstand", "Lohnbuchhaltung", "Drittland", "Nein"],
        column_header="| Gegenstand | Lohnbuchhaltung |",
        min_chars=80,
    ),
}
