"""Integration tests for the API audit log middleware.

Require a live PostgreSQL database (DATABASE_URL env var).
Each mutating request (POST/PUT/PATCH/DELETE) must produce exactly one
api_audit_log row; GET requests must not.
"""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import func, select

from tests.factories import create_case

pytestmark = pytest.mark.asyncio

_needs_db = pytest.mark.skipif(
    not os.environ.get("DATABASE_URL"), reason="DATABASE_URL not set"
)


async def _count_audit_rows(
    method: str | None = None, endpoint: str | None = None
) -> int:
    from app.database import async_session_factory
    from app.models._db.audit import APIAuditLogModel

    async with async_session_factory() as session:
        q = select(func.count()).select_from(APIAuditLogModel)
        if method:
            q = q.where(APIAuditLogModel.method == method)
        if endpoint:
            q = q.where(APIAuditLogModel.endpoint == endpoint)
        result = await session.execute(q)
        return result.scalar_one()


# ---------------------------------------------------------------------------
# POST writes an audit entry
# ---------------------------------------------------------------------------


@_needs_db
async def test_post_creates_audit_entry(client):
    before = await _count_audit_rows(method="POST")
    await create_case(client)
    after = await _count_audit_rows(method="POST")
    assert after == before + 1


# ---------------------------------------------------------------------------
# GET does not write an audit entry
# ---------------------------------------------------------------------------


@_needs_db
async def test_get_does_not_create_audit_entry(client):
    before = await _count_audit_rows()
    resp = await client.get("/api/v1/cases")
    assert resp.status_code == 200
    after = await _count_audit_rows()
    assert after == before


# ---------------------------------------------------------------------------
# Audit entry has correct fields
# ---------------------------------------------------------------------------


@_needs_db
async def test_audit_entry_fields(client):
    from app.database import async_session_factory
    from app.models._db.audit import APIAuditLogModel

    await create_case(client)

    async with async_session_factory() as session:
        result = await session.execute(
            select(APIAuditLogModel)
            .where(APIAuditLogModel.method == "POST")
            .order_by(APIAuditLogModel.timestamp.desc())
            .limit(1)
        )
        entry = result.scalar_one()

    assert entry.method == "POST"
    assert entry.endpoint == "/api/v1/cases"
    assert entry.status_code == 201
    assert entry.request_id != ""
    # user_id may be set (default user) or None depending on auth config
    assert entry.timestamp is not None


# ---------------------------------------------------------------------------
# UUID segments are collapsed to {id} in the endpoint
# ---------------------------------------------------------------------------


@_needs_db
async def test_uuid_path_segments_collapsed(client):
    from app.database import async_session_factory
    from app.models._db.audit import APIAuditLogModel

    case = await create_case(client)
    case_id = case["id"]

    patch_payload = {"title": "Geänderter Titel"}
    resp = await client.patch(f"/api/v1/cases/{case_id}", json=patch_payload)
    assert resp.status_code in (200, 204), resp.text

    async with async_session_factory() as session:
        result = await session.execute(
            select(APIAuditLogModel)
            .where(APIAuditLogModel.method == "PATCH")
            .order_by(APIAuditLogModel.timestamp.desc())
            .limit(1)
        )
        entry = result.scalar_one()

    assert "{id}" in entry.endpoint
    assert case_id not in entry.endpoint


# ---------------------------------------------------------------------------
# Middleware is fault-tolerant: DB failure must not break the response
# ---------------------------------------------------------------------------


async def test_audit_middleware_db_failure_does_not_break_response(client):
    """If the audit DB write fails, the original response is still returned."""
    broken_cm = MagicMock()
    broken_cm.__aenter__ = AsyncMock(side_effect=Exception("simulated DB failure"))
    broken_cm.__aexit__ = AsyncMock(return_value=False)

    with patch("app.main.async_session_factory", return_value=broken_cm):
        payload = {
            "title": "Fault-Toleranz-Test",
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

    # Response must succeed despite the audit log failure
    assert resp.status_code == 201, resp.text


# ---------------------------------------------------------------------------
# Phase 1 S6: hash chain, audited reads, failure accounting
# ---------------------------------------------------------------------------


async def _add_document(case_id: str, content: str = "Vertraulicher Text") -> str:
    import uuid

    from app.database import async_session_factory
    from app.models.db import DocumentModel

    async with async_session_factory() as session:
        doc = DocumentModel(
            case_id=uuid.UUID(case_id),
            name="doc.pdf",
            type="other",
            format="pdf",
            size_bytes=10,
            storage_path=f"test/{case_id}/doc.pdf",
            content=content,
        )
        session.add(doc)
        await session.commit()
        return str(doc.id)


@_needs_db
async def test_document_content_read_is_audited_with_resource_id(client):
    from app.database import async_session_factory
    from app.models._db.audit import APIAuditLogModel

    case = await create_case(client)
    doc_id = await _add_document(case["id"])
    before = await _count_audit_rows(method="GET")

    resp = await client.get(f"/api/v1/documents/{doc_id}/content")
    assert resp.status_code == 200

    assert await _count_audit_rows(method="GET") == before + 1
    async with async_session_factory() as session:
        entry = (
            await session.execute(
                select(APIAuditLogModel)
                .where(APIAuditLogModel.method == "GET")
                .order_by(APIAuditLogModel.seq.desc())
                .limit(1)
            )
        ).scalar_one()
    assert entry.endpoint == "/api/v1/documents/{id}/content"
    assert entry.resource_id == doc_id
    assert entry.entry_hash and len(entry.entry_hash) == 64


@_needs_db
async def test_failed_document_read_is_not_audited(client):
    before = await _count_audit_rows(method="GET")
    resp = await client.get(
        "/api/v1/documents/00000000-0000-0000-0000-000000000000/content"
    )
    assert resp.status_code == 404
    assert await _count_audit_rows(method="GET") == before


@_needs_db
async def test_chain_links_and_verifies(client):
    from app.database import async_session_factory
    from app.models._db.audit import APIAuditLogModel
    from app.services.audit_service import verify_audit_chain

    await create_case(client)
    await create_case(client)

    async with async_session_factory() as session:
        rows = (
            (
                await session.execute(
                    select(APIAuditLogModel)
                    .order_by(APIAuditLogModel.seq.desc())
                    .limit(2)
                )
            )
            .scalars()
            .all()
        )
        newest, previous = rows
        assert newest.prev_hash == previous.entry_hash
        result = await verify_audit_chain(session)
    assert result.ok, result
    assert result.checked >= 2


@_needs_db
async def test_tampering_breaks_chain(client):
    from sqlalchemy import update

    from app.database import async_session_factory
    from app.models._db.audit import APIAuditLogModel
    from app.services.audit_service import verify_audit_chain

    case = await create_case(client)
    async with async_session_factory() as session:
        victim = (
            await session.execute(
                select(APIAuditLogModel)
                .where(APIAuditLogModel.method == "POST")
                .order_by(APIAuditLogModel.seq.desc())
                .limit(1)
            )
        ).scalar_one()
        assert case["id"] not in victim.endpoint
        original_status = victim.status_code
        await session.execute(
            update(APIAuditLogModel)
            .where(APIAuditLogModel.id == victim.id)
            .values(status_code=418)
        )
        await session.commit()

    async with async_session_factory() as session:
        result = await verify_audit_chain(session)
        assert result.ok is False
        assert result.first_broken_seq == victim.seq
        assert "mismatch" in (result.reason or "")
        # Restore so later tests (and the chain) are intact again.
        await session.execute(
            update(APIAuditLogModel)
            .where(APIAuditLogModel.id == victim.id)
            .values(status_code=original_status)
        )
        await session.commit()

    async with async_session_factory() as session:
        assert (await verify_audit_chain(session)).ok


@_needs_db
async def test_audit_write_failure_is_counted_and_strict_mode_returns_500(
    client, monkeypatch
):
    from app.config import settings
    from app.core.metrics import api_audit_log_write_failures_total

    broken_cm = MagicMock()
    broken_cm.__aenter__ = AsyncMock(side_effect=Exception("simulated DB failure"))
    broken_cm.__aexit__ = AsyncMock(return_value=False)
    payload = {
        "title": "Strict-Audit-Test",
        "department": "IT",
        "case_type": "Softwareeinführung",
        "language": "de",
        "created_by": "test@example.com",
        "assignee": "DSB",
    }

    before = api_audit_log_write_failures_total._value.get()
    monkeypatch.setattr(settings, "audit_log_strict", False)
    with patch("app.main.async_session_factory", return_value=broken_cm):
        resp = await client.post("/api/v1/cases", json=payload)
    assert resp.status_code == 201
    assert api_audit_log_write_failures_total._value.get() == before + 1

    monkeypatch.setattr(settings, "audit_log_strict", True)
    with patch("app.main.async_session_factory", return_value=broken_cm):
        resp = await client.post("/api/v1/cases", json=payload)
    assert resp.status_code == 500
    assert "Audit log" in resp.json()["title"]
