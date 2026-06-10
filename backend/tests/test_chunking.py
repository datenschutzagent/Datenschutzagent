"""Unit tests for structure-aware chunking (weaviate_service.chunk_text), B4.

No Weaviate, LLM or DB needed — pure text logic.
"""
from app.services.weaviate_service import chunk_text

_TABLE = """--- Sheet: VVT ---
| A | B | C |
| --- | --- | --- |
| Zweck | x | Art. 6 Abs. 1 lit. f DSGVO |
| Lohnabrechnung | y | Art. 6 Abs. 1 lit. c DSGVO |
| Bewerbermanagement | z | Art. 6 Abs. 1 lit. b DSGVO |
| Vertragsdaten | w | Art. 6 Abs. 1 lit. b DSGVO |
| Newsletter | v | Art. 6 Abs. 1 lit. a DSGVO |"""


def _table_lines(chunk: str) -> list[str]:
    return [ln for ln in chunk.splitlines() if ln.strip().startswith("|")]


def test_large_table_split_repeats_header_and_label():
    # Small chunk size forces the table to span multiple chunks.
    chunks = chunk_text(_TABLE, chunk_size=120, overlap=0)
    assert len(chunks) >= 2
    # Every chunk carries the column-letter header + sheet label so "Spalte C" stays meaningful.
    for c in chunks:
        assert "| A | B | C |" in c
        assert "--- Sheet: VVT ---" in c


def test_table_rows_are_never_split_mid_row():
    chunks = chunk_text(_TABLE, chunk_size=120, overlap=0)
    for c in chunks:
        for line in _table_lines(c):
            # A complete Markdown row starts and ends with a pipe.
            assert line.strip().startswith("|") and line.strip().endswith("|")


def test_all_table_data_survives_chunking():
    chunks = chunk_text(_TABLE, chunk_size=120, overlap=0)
    joined = "\n".join(chunks)
    for token in ("Lohnabrechnung", "Bewerbermanagement", "Vertragsdaten", "Newsletter"):
        assert token in joined


def test_small_table_stays_single_chunk_with_header():
    chunks = chunk_text(_TABLE, chunk_size=10000, overlap=0)
    assert len(chunks) == 1
    assert "| A | B | C |" in chunks[0]


def test_prose_only_text_is_sentence_chunked_without_table_artifacts():
    text = "Erster Satz hier. Zweiter Satz hier. " * 50
    chunks = chunk_text(text.strip(), chunk_size=200, overlap=20)
    assert len(chunks) > 1
    assert all("| A | B | C |" not in c for c in chunks)
    assert all("--- Sheet:" not in c for c in chunks)


def test_mixed_prose_and_table_are_segmented():
    mixed = "Einleitender Absatz zur Verarbeitung.\n\n" + _TABLE
    chunks = chunk_text(mixed, chunk_size=120, overlap=0)
    assert any("Einleitender Absatz" in c for c in chunks)
    assert any("| A | B | C |" in c for c in chunks)
    # The prose chunk must not drag the table header into it.
    prose_chunks = [c for c in chunks if "Einleitender Absatz" in c]
    assert all("| A | B | C |" not in c for c in prose_chunks)
