"""Integration tests for the /api/v1/legal-bases routes.

Covers ``app/api/routes/legal_bases.py``: CRUD for Rechtsgrundlagen, the
``applicability`` filter and ``skip``/``limit`` pagination. Weaviate indexing is
disabled in the test environment (``WEAVIATE_INDEXING_ENABLED`` defaults to
false), so ``index_legal_base`` is a no-op; chunk deletion is patched where the
call itself is asserted. Requires a live PostgreSQL (``DATABASE_URL``).
"""

from __future__ import annotations

import uuid
from typing import Any
from unittest.mock import MagicMock

import pytest

pytestmark = pytest.mark.asyncio

BASE = "/api/v1/legal-bases"
UNKNOWN_ID = "00000000-0000-0000-0000-000000000000"


def _uniq(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


async def create_legal_base(client, **overrides: Any) -> dict:
    payload: dict[str, Any] = {
        "title": _uniq("Art. 6 Abs. 1 lit. b DSGVO"),
        "short_name": "Art. 6(1)(b)",
        "content": "Verarbeitung ist zur Erfüllung eines Vertrags erforderlich.",
        "applicability": "always",
        "department_codes": None,
        "case_types": None,
        "internal_only": False,
        **overrides,
    }
    resp = await client.post(BASE, json=payload)
    assert resp.status_code == 201, f"{BASE}: {resp.status_code} {resp.text}"
    return resp.json()


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------


async def test_create_legal_base_returns_full_record(client):
    title = _uniq("§ 26 BDSG")
    base = await create_legal_base(
        client,
        title=title,
        short_name="§ 26 BDSG",
        content="Datenverarbeitung für Zwecke des Beschäftigungsverhältnisses.",
        applicability="conditional",
        department_codes=["HR", "IT"],
        case_types=["Onboarding"],
        internal_only=True,
    )
    assert base["id"]
    assert base["title"] == title
    assert base["short_name"] == "§ 26 BDSG"
    assert base["content"].startswith("Datenverarbeitung")
    assert base["applicability"] == "conditional"
    assert base["department_codes"] == ["HR", "IT"]
    assert base["case_types"] == ["Onboarding"]
    assert base["internal_only"] is True
    assert base["created_at"] and base["updated_at"]


async def test_create_legal_base_minimal_payload_uses_defaults(client):
    title = _uniq("Minimal")
    resp = await client.post(BASE, json={"title": title})
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["title"] == title
    assert data["short_name"] is None
    assert data["content"] == ""
    assert data["applicability"] == "always"
    # None in the DB is coerced to an empty list in the response
    assert data["department_codes"] == []
    assert data["case_types"] == []
    assert data["internal_only"] is False


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"title": ""},
        {"title": "x" * 501},
        {"title": "Bad applicability", "applicability": "sometimes"},
        {"title": "Bad short name", "short_name": "s" * 101},
        {"title": "Bad codes", "department_codes": "HR"},
        {"title": "Bad flag", "internal_only": "maybe"},
    ],
)
async def test_create_legal_base_invalid_payload_returns_422(client, payload):
    resp = await client.post(BASE, json=payload)
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Get
# ---------------------------------------------------------------------------


async def test_get_legal_base_by_id(client):
    base = await create_legal_base(client)
    resp = await client.get(f"{BASE}/{base['id']}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == base["id"]
    assert data["title"] == base["title"]
    assert data["content"] == base["content"]


async def test_get_legal_base_unknown_returns_404(client):
    resp = await client.get(f"{BASE}/{UNKNOWN_ID}")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Legal base not found"


async def test_get_legal_base_invalid_uuid_returns_422(client):
    resp = await client.get(f"{BASE}/not-a-uuid")
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# List + filter + pagination
# ---------------------------------------------------------------------------


async def test_list_legal_bases_includes_created(client):
    base = await create_legal_base(client)
    resp = await client.get(BASE)
    assert resp.status_code == 200
    ids = {b["id"] for b in resp.json()}
    assert base["id"] in ids


async def test_list_legal_bases_sorted_by_title(client):
    prefix = _uniq("Sort")
    await create_legal_base(client, title=f"{prefix}-C")
    await create_legal_base(client, title=f"{prefix}-A")
    await create_legal_base(client, title=f"{prefix}-B")

    resp = await client.get(BASE, params={"limit": 1000})
    assert resp.status_code == 200
    titles = [b["title"] for b in resp.json() if b["title"].startswith(prefix)]
    assert titles == sorted(titles)
    assert len(titles) == 3


async def test_list_legal_bases_filter_by_applicability(client):
    always = await create_legal_base(client, applicability="always")
    conditional = await create_legal_base(client, applicability="conditional")

    resp = await client.get(
        BASE, params={"applicability": "conditional", "limit": 1000}
    )
    assert resp.status_code == 200
    data = resp.json()
    ids = {b["id"] for b in data}
    assert conditional["id"] in ids
    assert always["id"] not in ids
    assert all(b["applicability"] == "conditional" for b in data)

    resp = await client.get(BASE, params={"applicability": "always", "limit": 1000})
    assert resp.status_code == 200
    data = resp.json()
    ids = {b["id"] for b in data}
    assert always["id"] in ids
    assert conditional["id"] not in ids
    assert all(b["applicability"] == "always" for b in data)


async def test_list_legal_bases_invalid_applicability_returns_422(client):
    resp = await client.get(BASE, params={"applicability": "never"})
    assert resp.status_code == 422


async def test_list_legal_bases_pagination_skip_and_limit(client):
    prefix = _uniq("Page")
    for suffix in ("1", "2", "3"):
        await create_legal_base(client, title=f"{prefix}-{suffix}")

    full = await client.get(BASE, params={"limit": 1000})
    assert full.status_code == 200
    all_ids = [b["id"] for b in full.json()]
    assert len(all_ids) >= 3

    # limit slices the ordered list from the start …
    limited = await client.get(BASE, params={"limit": 2})
    assert limited.status_code == 200
    assert [b["id"] for b in limited.json()] == all_ids[:2]

    # … and skip offsets it.
    skipped = await client.get(BASE, params={"skip": 1, "limit": 2})
    assert skipped.status_code == 200
    assert [b["id"] for b in skipped.json()] == all_ids[1:3]

    # skipping past the end yields an empty page
    beyond = await client.get(BASE, params={"skip": len(all_ids) + 10})
    assert beyond.status_code == 200
    assert beyond.json() == []


@pytest.mark.parametrize(
    "params",
    [
        {"skip": -1},
        {"limit": 0},
        {"limit": 1001},
        {"skip": "abc"},
    ],
)
async def test_list_legal_bases_invalid_pagination_returns_422(client, params):
    resp = await client.get(BASE, params=params)
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Update
# ---------------------------------------------------------------------------


async def test_update_legal_base_partial_fields(client):
    base = await create_legal_base(client, applicability="always")
    new_title = _uniq("Aktualisiert")
    resp = await client.patch(
        f"{BASE}/{base['id']}",
        json={
            "title": new_title,
            "content": "Neuer Inhalt",
            "applicability": "conditional",
            "department_codes": ["FIN"],
            "internal_only": True,
        },
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["id"] == base["id"]
    assert data["title"] == new_title
    assert data["content"] == "Neuer Inhalt"
    assert data["applicability"] == "conditional"
    assert data["department_codes"] == ["FIN"]
    assert data["internal_only"] is True
    # untouched fields keep their value
    assert data["short_name"] == base["short_name"]
    assert data["case_types"] == []

    fetched = await client.get(f"{BASE}/{base['id']}")
    assert fetched.json()["title"] == new_title
    assert fetched.json()["applicability"] == "conditional"


async def test_update_legal_base_empty_body_is_noop(client):
    base = await create_legal_base(client)
    resp = await client.patch(f"{BASE}/{base['id']}", json={})
    assert resp.status_code == 200
    data = resp.json()
    assert data["title"] == base["title"]
    assert data["content"] == base["content"]
    assert data["applicability"] == base["applicability"]


async def test_update_legal_base_can_clear_optional_fields(client):
    base = await create_legal_base(
        client, short_name="Kurz", department_codes=["HR"], case_types=["X"]
    )
    resp = await client.patch(
        f"{BASE}/{base['id']}",
        json={"short_name": None, "department_codes": None, "case_types": None},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["short_name"] is None
    assert data["department_codes"] == []
    assert data["case_types"] == []


async def test_update_legal_base_unknown_returns_404(client):
    resp = await client.patch(f"{BASE}/{UNKNOWN_ID}", json={"title": "Neu"})
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Legal base not found"


@pytest.mark.parametrize(
    "payload",
    [
        {"title": ""},
        {"title": "x" * 501},
        {"applicability": "whenever"},
        {"internal_only": "nope"},
        {"department_codes": "HR"},
    ],
)
async def test_update_legal_base_invalid_payload_returns_422(client, payload):
    base = await create_legal_base(client)
    resp = await client.patch(f"{BASE}/{base['id']}", json=payload)
    assert resp.status_code == 422
    # record is unchanged
    fetched = await client.get(f"{BASE}/{base['id']}")
    assert fetched.json()["title"] == base["title"]


async def test_update_legal_base_triggers_reindex(client, monkeypatch):
    calls: list[tuple] = []
    monkeypatch.setattr(
        "app.api.routes.legal_bases.index_legal_base",
        lambda *args: calls.append(args) or True,
    )
    base = await create_legal_base(client)
    assert len(calls) == 1  # create indexes once
    resp = await client.patch(f"{BASE}/{base['id']}", json={"content": "Neu"})
    assert resp.status_code == 200
    assert len(calls) == 2
    legal_base_id, title, content = calls[-1]
    assert str(legal_base_id) == base["id"]
    assert title == base["title"]
    assert content == "Neu"


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------


async def test_delete_legal_base(client, monkeypatch):
    delete_chunks = MagicMock(return_value=True)
    monkeypatch.setattr(
        "app.api.routes.legal_bases.delete_legal_base_chunks", delete_chunks
    )
    base = await create_legal_base(client)

    resp = await client.delete(f"{BASE}/{base['id']}")
    assert resp.status_code == 204
    delete_chunks.assert_called_once()
    assert str(delete_chunks.call_args.args[0]) == base["id"]

    get_resp = await client.get(f"{BASE}/{base['id']}")
    assert get_resp.status_code == 404

    listing = await client.get(BASE, params={"limit": 1000})
    assert base["id"] not in {b["id"] for b in listing.json()}


async def test_delete_legal_base_unknown_returns_404(client, monkeypatch):
    delete_chunks = MagicMock(return_value=True)
    monkeypatch.setattr(
        "app.api.routes.legal_bases.delete_legal_base_chunks", delete_chunks
    )
    resp = await client.delete(f"{BASE}/{UNKNOWN_ID}")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Legal base not found"
    delete_chunks.assert_not_called()


async def test_delete_legal_base_twice_returns_404(client, monkeypatch):
    monkeypatch.setattr(
        "app.api.routes.legal_bases.delete_legal_base_chunks",
        MagicMock(return_value=True),
    )
    base = await create_legal_base(client)
    assert (await client.delete(f"{BASE}/{base['id']}")).status_code == 204
    assert (await client.delete(f"{BASE}/{base['id']}")).status_code == 404


async def test_delete_legal_base_without_weaviate_still_succeeds(client):
    """Weaviate is not reachable in tests: chunk deletion degrades to a no-op."""
    base = await create_legal_base(client)
    resp = await client.delete(f"{BASE}/{base['id']}")
    assert resp.status_code == 204
    assert (await client.get(f"{BASE}/{base['id']}")).status_code == 404
