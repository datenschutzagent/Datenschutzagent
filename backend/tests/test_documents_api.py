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
        files={
            "file": (
                filename,
                data,
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
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
        data={
            "case_id": "00000000-0000-0000-0000-000000000000",
            "document_type": "other",
        },
        files={
            "file": (
                "test.docx",
                _make_docx_bytes(),
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
    )
    assert resp.status_code == 404


async def test_upload_document_auto_increments_version(client):
    case = await _create_case(client, title="Version Test")
    doc1 = await _upload_document(client, case["id"], filename="vvt_v1.docx")
    doc2_resp = await client.post(
        "/api/v1/documents",
        data={"case_id": case["id"], "document_type": doc1["type"]},
        files={
            "file": (
                "vvt_v2.docx",
                _make_docx_bytes(),
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
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


# ---------------------------------------------------------------------------
# Phase 2 R6: pagination, unique version constraint, version-collision retry
# ---------------------------------------------------------------------------


async def test_list_documents_pagination(client):
    case = await _create_case(client, title="Pagination Test")
    await _upload_document(client, case["id"], filename="a.docx")
    await _upload_document(client, case["id"], filename="b.docx")
    first = await client.get(
        "/api/v1/documents", params={"case_id": case["id"], "limit": 1}
    )
    assert first.status_code == 200
    assert len(first.json()) == 1
    second = await client.get(
        "/api/v1/documents", params={"case_id": case["id"], "limit": 1, "skip": 1}
    )
    assert len(second.json()) == 1
    assert first.json()[0]["id"] != second.json()[0]["id"]
    too_many = await client.get("/api/v1/documents", params={"limit": 5000})
    assert too_many.status_code == 422


async def test_duplicate_version_is_rejected_by_database(client):
    import uuid

    from sqlalchemy.exc import IntegrityError

    from app.database import async_session_factory
    from app.models.db import DocumentModel

    case = await _create_case(client, title="Unique Version")
    doc = await _upload_document(client, case["id"], filename="v.docx")
    async with async_session_factory() as session:
        session.add(
            DocumentModel(
                case_id=uuid.UUID(case["id"]),
                name="dup.docx",
                type=doc["type"],
                version=doc["version"],
                format="docx",
                size_bytes=1,
                storage_path="x",
            )
        )
        with pytest.raises(IntegrityError):
            await session.commit()


async def test_upload_retries_on_version_collision(client, monkeypatch):
    """A stale max(version) (parallel upload) must not produce a 500 or a duplicate."""
    from app.api.routes import documents as documents_route

    case = await _create_case(client, title="Version Collision")
    first = await _upload_document(client, case["id"], filename="one.docx")
    real_next = documents_route._next_version_for_type
    calls: list[int] = []

    async def _stale_then_real(db, case_id, document_type):
        real = await real_next(db, case_id, document_type)
        calls.append(real)
        return first["version"] if len(calls) == 1 else real  # first answer is stale

    monkeypatch.setattr(documents_route, "_next_version_for_type", _stale_then_real)
    second = await _upload_document(client, case["id"], filename="two.docx")
    assert second["version"] == first["version"] + 1
    assert len(calls) == 2


async def test_case_activities_pagination(client):
    case = await _create_case(client, title="Activities Pagination")
    resp = await client.get(
        f"/api/v1/cases/{case['id']}/activities", params={"limit": 1}
    )
    assert resp.status_code == 200
    assert len(resp.json()) <= 1
    bad = await client.get(
        f"/api/v1/cases/{case['id']}/activities", params={"limit": 0}
    )
    assert bad.status_code == 422


async def test_bulk_upload_isolates_failing_file(client, monkeypatch):
    """One broken file must not take the other files of the batch down (savepoints)."""
    from app.api.routes import documents as documents_route

    case = await _create_case(client, title="Bulk Isolation")
    real_save = documents_route.save_file

    def _save(case_id, doc_id, filename, content):
        if filename == "bad.docx":
            raise RuntimeError("storage exploded")
        return real_save(case_id, doc_id, filename, content)

    monkeypatch.setattr(documents_route, "save_file", _save)
    mime = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    resp = await client.post(
        "/api/v1/documents/bulk",
        data={"case_id": case["id"], "document_type": "other"},
        files=[
            ("files", ("good.docx", _make_docx_bytes(), mime)),
            ("files", ("bad.docx", _make_docx_bytes(), mime)),
            ("files", ("good2.docx", _make_docx_bytes(), mime)),
        ],
    )
    assert resp.status_code == 201, resp.text
    names = sorted(d["name"] for d in resp.json())
    assert names == ["good.docx", "good2.docx"]
    # The failed file left no row behind and did not leak its error text.
    listed = await client.get("/api/v1/documents", params={"case_id": case["id"]})
    assert sorted(d["name"] for d in listed.json()) == ["good.docx", "good2.docx"]
    assert "storage exploded" not in resp.text
