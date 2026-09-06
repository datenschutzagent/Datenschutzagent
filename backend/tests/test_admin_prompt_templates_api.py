"""Integration tests for /api/v1/admin/prompt-templates (requires DATABASE_URL).

The set of valid keys is fixed (``VALID_PROMPT_KEYS``) and the database is shared
across the whole suite, so every test purges the rows of the key it works on
before exercising the endpoint. Keys are spread across tests to keep them
independent of each other's leftovers.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import delete, select

from app.services.prompt_template_service import (
    PROMPT_TEMPLATE_KEY_META,
    VALID_PROMPT_KEYS,
    _cache,
    _cache_key,
    get_active_template,
)

pytestmark = pytest.mark.asyncio

BASE = "/api/v1/admin/prompt-templates"


async def _purge_key(key: str) -> None:
    """Remove every stored version for ``key`` so version numbering is deterministic."""
    from app.database import async_session_factory
    from app.models.db import PromptTemplateModel

    async with async_session_factory() as session:
        await session.execute(
            delete(PromptTemplateModel).where(PromptTemplateModel.key == key)
        )
        await session.commit()


async def _rows_for_key(key: str) -> list:
    from app.database import async_session_factory
    from app.models.db import PromptTemplateModel

    async with async_session_factory() as session:
        result = await session.execute(
            select(PromptTemplateModel).where(PromptTemplateModel.key == key)
        )
        return result.scalars().all()


def _content() -> str:
    return f"Prompt {uuid.uuid4()} mit {{language_hint}}"


# ---------------------------------------------------------------------------
# GET /keys
# ---------------------------------------------------------------------------


async def test_keys_returns_metadata_for_all_prompt_keys(client):
    resp = await client.get(f"{BASE}/keys")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert {m["key"] for m in body} == VALID_PROMPT_KEYS
    assert len(body) == len(PROMPT_TEMPLATE_KEY_META)
    vvt_user = next(m for m in body if m["key"] == "vvt_user")
    assert vvt_user["placeholders"] == ["field_list", "document_text"]
    assert vvt_user["description"]


# ---------------------------------------------------------------------------
# GET /versions
# ---------------------------------------------------------------------------


async def test_versions_requires_key_query_param(client):
    resp = await client.get(f"{BASE}/versions")
    assert resp.status_code == 422


async def test_versions_rejects_unknown_key(client):
    resp = await client.get(f"{BASE}/versions", params={"key": "does_not_exist"})
    assert resp.status_code == 400
    assert resp.json()["detail"] == "Invalid prompt template key"


async def test_versions_lists_all_versions_newest_first(client):
    key = "check_rag_document_system"
    await _purge_key(key)
    for version in ("1.0", "1.1", "2.0"):
        resp = await client.post(
            BASE,
            json={"key": key, "version": version, "content": _content()},
        )
        assert resp.status_code == 201, resp.text

    resp = await client.get(f"{BASE}/versions", params={"key": key})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert [v["version"] for v in body] == ["2.0", "1.1", "1.0"]
    assert [v["is_active"] for v in body] == [True, False, False]
    assert all(v["key"] == key for v in body)


# ---------------------------------------------------------------------------
# GET "" (active templates)
# ---------------------------------------------------------------------------


async def test_list_rejects_unknown_key_filter(client):
    resp = await client.get(BASE, params={"key": "nope"})
    assert resp.status_code == 400


async def test_list_rejects_empty_key_filter(client):
    resp = await client.get(BASE, params={"key": ""})
    assert resp.status_code == 422


async def test_list_returns_only_active_templates(client):
    key = "check_rag_document_user"
    await _purge_key(key)
    inactive = await client.post(
        BASE,
        json={"key": key, "content": _content(), "set_active": False},
    )
    assert inactive.status_code == 201, inactive.text
    active = await client.post(BASE, json={"key": key, "content": _content()})
    assert active.status_code == 201, active.text

    filtered = await client.get(BASE, params={"key": key})
    assert filtered.status_code == 200, filtered.text
    assert [t["id"] for t in filtered.json()] == [active.json()["id"]]

    unfiltered = await client.get(BASE)
    assert unfiltered.status_code == 200
    ids = {t["id"] for t in unfiltered.json()}
    assert active.json()["id"] in ids
    assert inactive.json()["id"] not in ids
    assert all(t["is_active"] for t in unfiltered.json())


# ---------------------------------------------------------------------------
# POST ""
# ---------------------------------------------------------------------------


async def test_create_rejects_unknown_key(client):
    resp = await client.post(BASE, json={"key": "unknown_key", "content": "x"})
    assert resp.status_code == 400
    assert resp.json()["detail"] == "Invalid prompt template key"


@pytest.mark.parametrize(
    "payload",
    [
        {"content": "x"},  # key missing
        {"key": "vvt_system"},  # content missing
        {"key": "vvt_system", "content": ""},  # content too short
        {"key": "", "content": "x"},  # key too short
        {"key": "vvt_system", "content": "x", "version": "v" * 51},  # version too long
    ],
)
async def test_create_validation_errors(client, payload):
    resp = await client.post(BASE, json=payload)
    assert resp.status_code == 422, resp.text


async def test_create_first_version_defaults_to_1_0_and_is_active(client):
    key = "check_full_text_document_system"
    await _purge_key(key)
    content = _content()

    resp = await client.post(BASE, json={"key": key, "content": content})
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["version"] == "1.0"
    assert body["is_active"] is True
    assert body["key"] == key
    assert body["content"] == content
    uuid.UUID(body["id"])
    assert body["created_at"]


async def test_create_auto_increments_minor_version(client):
    key = "check_full_text_document_user"
    await _purge_key(key)
    first = await client.post(BASE, json={"key": key, "content": _content()})
    assert first.json()["version"] == "1.0"

    second = await client.post(BASE, json={"key": key, "content": _content()})
    assert second.status_code == 201, second.text
    assert second.json()["version"] == "1.1"

    explicit = await client.post(
        BASE, json={"key": key, "version": "3.7", "content": _content()}
    )
    assert explicit.status_code == 201
    third = await client.post(BASE, json={"key": key, "content": _content()})
    assert third.json()["version"] == "3.8"


async def test_create_falls_back_to_timestamp_version_when_last_is_unparseable(
    client,
):
    key = "check_full_text_cross_system"
    await _purge_key(key)
    weird = await client.post(
        BASE, json={"key": key, "version": "2.x", "content": _content()}
    )
    assert weird.status_code == 201, weird.text

    resp = await client.post(BASE, json={"key": key, "content": _content()})
    assert resp.status_code == 201, resp.text
    version = resp.json()["version"]
    assert version.startswith("v-")
    # v-YYYYMMDD-HHMM
    assert len(version) == len("v-20260101-1200")


async def test_create_rejects_duplicate_key_version(client):
    key = "check_full_text_cross_user"
    await _purge_key(key)
    first = await client.post(
        BASE, json={"key": key, "version": "1.0", "content": _content()}
    )
    assert first.status_code == 201, first.text

    dup = await client.post(
        BASE, json={"key": key, "version": "1.0", "content": _content()}
    )
    assert dup.status_code == 409
    assert dup.json()["detail"] == "This key and version already exist"
    assert len(await _rows_for_key(key)) == 1


async def test_create_with_set_active_deactivates_previous_versions(client):
    key = "check_rag_cross_system"
    await _purge_key(key)
    old = await client.post(BASE, json={"key": key, "content": _content()})
    assert old.json()["is_active"] is True

    new = await client.post(BASE, json={"key": key, "content": _content()})
    assert new.status_code == 201
    assert new.json()["is_active"] is True

    rows = {str(r.id): r.is_active for r in await _rows_for_key(key)}
    assert rows == {old.json()["id"]: False, new.json()["id"]: True}


async def test_create_without_set_active_keeps_existing_active_version(client):
    key = "check_rag_cross_user"
    await _purge_key(key)
    active = await client.post(BASE, json={"key": key, "content": _content()})

    draft = await client.post(
        BASE, json={"key": key, "content": _content(), "set_active": False}
    )
    assert draft.status_code == 201, draft.text
    assert draft.json()["is_active"] is False

    rows = {str(r.id): r.is_active for r in await _rows_for_key(key)}
    assert rows[active.json()["id"]] is True
    assert rows[draft.json()["id"]] is False


async def test_create_invalidates_cache_and_new_content_is_served(client):
    key = "vvt_system"
    await _purge_key(key)
    _cache[_cache_key(key)] = "stale cached content"
    content = _content()

    resp = await client.post(BASE, json={"key": key, "content": content})
    assert resp.status_code == 201, resp.text
    assert _cache_key(key) not in _cache
    assert await get_active_template(key) == content
    _cache.pop(_cache_key(key), None)


# ---------------------------------------------------------------------------
# PATCH /{template_id}
# ---------------------------------------------------------------------------


async def test_update_unknown_template_returns_404(client):
    resp = await client.patch(f"{BASE}/{uuid.uuid4()}", json={"is_active": True})
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Prompt template not found"


async def test_update_rejects_invalid_uuid(client):
    resp = await client.patch(f"{BASE}/not-a-uuid", json={"is_active": True})
    assert resp.status_code == 422


async def test_update_rejects_wrong_type(client):
    resp = await client.patch(
        f"{BASE}/{uuid.uuid4()}", json={"is_active": "definitely"}
    )
    assert resp.status_code == 422


async def test_update_activates_version_and_deactivates_siblings(client):
    key = "vvt_user"
    await _purge_key(key)
    v1 = await client.post(BASE, json={"key": key, "content": _content()})
    v2 = await client.post(BASE, json={"key": key, "content": _content()})
    assert v2.json()["is_active"] is True
    _cache[_cache_key(key)] = "stale"

    resp = await client.patch(f"{BASE}/{v1.json()['id']}", json={"is_active": True})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["id"] == v1.json()["id"]
    assert body["is_active"] is True
    assert _cache_key(key) not in _cache

    rows = {str(r.id): r.is_active for r in await _rows_for_key(key)}
    assert rows == {v1.json()["id"]: True, v2.json()["id"]: False}

    listed = await client.get(BASE, params={"key": key})
    assert [t["id"] for t in listed.json()] == [v1.json()["id"]]


async def test_update_without_activation_leaves_state_untouched(client):
    key = "vvt_user"
    await _purge_key(key)
    active = await client.post(BASE, json={"key": key, "content": _content()})
    draft = await client.post(
        BASE, json={"key": key, "content": _content(), "set_active": False}
    )

    empty = await client.patch(f"{BASE}/{draft.json()['id']}", json={})
    assert empty.status_code == 200, empty.text
    assert empty.json()["is_active"] is False

    explicit_false = await client.patch(
        f"{BASE}/{active.json()['id']}", json={"is_active": False}
    )
    assert explicit_false.status_code == 200
    # Only activation is supported; is_active=false is a no-op by design.
    assert explicit_false.json()["is_active"] is True

    rows = {str(r.id): r.is_active for r in await _rows_for_key(key)}
    assert rows[active.json()["id"]] is True
    assert rows[draft.json()["id"]] is False
