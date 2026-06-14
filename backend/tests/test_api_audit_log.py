"""Integration tests for the API audit log middleware.

Require a live PostgreSQL database (DATABASE_URL env var).
Each mutating request (POST/PUT/PATCH/DELETE) must produce exactly one
api_audit_log row; GET requests must not.
"""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import func, select

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


async def _create_case(client) -> dict:
    payload = {
        "title": "Audit-Log-Test-Vorgang",
        "department": "IT",
        "case_type": "Softwareeinführung",
        "language": "de",
        "created_by": "audit-test@example.com",
        "assignee": "DSB",
        "processing_context": None,
        "special_category_data": False,
        "international_transfer": False,
    }
    resp = await client.post("/api/v1/cases", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


# ---------------------------------------------------------------------------
# POST writes an audit entry
# ---------------------------------------------------------------------------


@_needs_db
async def test_post_creates_audit_entry(client):
    before = await _count_audit_rows(method="POST")
    await _create_case(client)
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

    await _create_case(client)

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

    case = await _create_case(client)
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
