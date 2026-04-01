"""Integration tests for the /api/v1/documents routes.

These tests require a live PostgreSQL database (DATABASE_URL env var).
They test upload, list, retrieve, and delete behaviour for documents.
"""
import io

import pytest

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_docx_bytes() -> bytes:
    """Create a minimal in-memory DOCX file for upload testing."""
    from docx import Document

    doc = Document()
    doc.add_paragraph("Test document content for integration tests.")
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


async def _create_case(client, title: str = "Test-Vorgang") -> dict:
    payload = {
        "title": title,
        "department": "IT",
        "case_type": "Softwareeinführung",
        "language": "de",
        "created_by": "test@example.com",
        "assignee": "DSB",
        "processing_context": None,
        "special_category_data": False,
        "international_transfer": False,
    }
    resp = await client.post("/api/v1/cases", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _upload_document(client, case_id: str, filename: str = "test.docx") -> dict:
    data = _make_docx_bytes()
    resp = await client.post(
        "/api/v1/documents",
        data={"case_id": case_id, "document_type": "other", "uploaded_by": "tester"},
        files={"file": (filename, data, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


# ---------------------------------------------------------------------------
# Upload
# ---------------------------------------------------------------------------


async def test_upload_document_returns_id(client):
    case = await _create_case(client, title="Upload Test")
    doc = await _upload_document(client, case["id"])
    assert "id" in doc
    assert doc["case_id"] == case["id"]
    assert doc["name"] == "test.docx"
    assert doc["format"] == "docx"


async def test_upload_document_unsupported_format_returns_400(client):
    case = await _create_case(client, title="Bad Format Test")
    resp = await client.post(
        "/api/v1/documents",
        data={"case_id": case["id"], "document_type": "other"},
        files={"file": ("notes.txt", b"some text", "text/plain")},
    )
    assert resp.status_code == 400


async def test_upload_document_nonexistent_case_returns_404(client):
    resp = await client.post(
        "/api/v1/documents",
        data={"case_id": "00000000-0000-0000-0000-000000000000", "document_type": "other"},
        files={"file": ("test.docx", _make_docx_bytes(), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
    )
    assert resp.status_code == 404


async def test_upload_document_auto_increments_version(client):
    case = await _create_case(client, title="Version Test")
    doc1 = await _upload_document(client, case["id"], filename="vvt_v1.docx")
    doc2_resp = await client.post(
        "/api/v1/documents",
        data={"case_id": case["id"], "document_type": doc1["type"]},
        files={"file": ("vvt_v2.docx", _make_docx_bytes(), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
    )
    assert doc2_resp.status_code == 201
    doc2 = doc2_resp.json()
    assert doc2["version"] == doc1["version"] + 1


# ---------------------------------------------------------------------------
# List
# ---------------------------------------------------------------------------


async def test_list_documents_empty_for_new_case(client):
    case = await _create_case(client, title="Empty Docs Test")
    resp = await client.get("/api/v1/documents", params={"case_id": case["id"]})
    assert resp.status_code == 200
    assert resp.json() == []


async def test_list_documents_includes_uploaded(client):
    case = await _create_case(client, title="List Docs Test")
    doc = await _upload_document(client, case["id"])
    resp = await client.get("/api/v1/documents", params={"case_id": case["id"]})
    assert resp.status_code == 200
    doc_ids = [d["id"] for d in resp.json()]
    assert doc["id"] in doc_ids


# ---------------------------------------------------------------------------
# Get single document
# ---------------------------------------------------------------------------


async def test_get_document_by_id(client):
    case = await _create_case(client, title="Get Doc Test")
    doc = await _upload_document(client, case["id"])
    resp = await client.get(f"/api/v1/documents/{doc['id']}")
    assert resp.status_code == 200
    assert resp.json()["id"] == doc["id"]


async def test_get_document_not_found(client):
    resp = await client.get("/api/v1/documents/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404


async def test_get_document_content(client):
    case = await _create_case(client, title="Content Test")
    doc = await _upload_document(client, case["id"])
    resp = await client.get(f"/api/v1/documents/{doc['id']}/content")
    assert resp.status_code == 200
    data = resp.json()
    assert "content" in data
    assert "extraction_status" in data


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------


async def test_delete_document_returns_204(client):
    case = await _create_case(client, title="Delete Doc Test")
    doc = await _upload_document(client, case["id"])
    resp = await client.delete(f"/api/v1/documents/{doc['id']}")
    assert resp.status_code == 204


async def test_delete_document_then_get_returns_404(client):
    case = await _create_case(client, title="Delete Verify Test")
    doc = await _upload_document(client, case["id"])
    await client.delete(f"/api/v1/documents/{doc['id']}")
    resp = await client.get(f"/api/v1/documents/{doc['id']}")
    assert resp.status_code == 404


async def test_delete_nonexistent_document_returns_404(client):
    resp = await client.delete("/api/v1/documents/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404
