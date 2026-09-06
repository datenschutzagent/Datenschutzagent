"""Integration tests for the /api/v1/playbooks routes.

These tests require a live PostgreSQL database (DATABASE_URL env var). They cover
CRUD, revision history / restore, wizard selection ranking and the coverage preview.
Playbooks are created through the API with unique names because the database is shared
and not transactionally isolated.
"""

import uuid

import pytest

from tests.factories import create_case

pytestmark = pytest.mark.asyncio

NIL_UUID = "00000000-0000-0000-0000-000000000000"

DEFAULT_CHECKS = [
    {
        "name": "Rechtsgrundlage dokumentiert",
        "category": "Rechtsgrundlage",
        "instruction": "Prüfe, ob eine Rechtsgrundlage genannt wird.",
        "scope": "document",
    }
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _unique(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


async def _create_playbook(client, *, checks=None, **overrides) -> dict:
    payload = {
        "name": _unique("PB"),
        "version": "1.0",
        "content": {"checks": DEFAULT_CHECKS if checks is None else checks},
        **overrides,
    }
    resp = await client.post("/api/v1/playbooks", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _add_document(case_id: str, doc_type: str) -> None:
    from app.database import async_session_factory
    from app.models.db import DocumentModel

    async with async_session_factory() as session:
        session.add(
            DocumentModel(
                case_id=uuid.UUID(case_id),
                name=f"{doc_type}.pdf",
                type=doc_type,
                format="pdf",
                size_bytes=10,
                storage_path=f"test/{case_id}/{doc_type}.pdf",
            )
        )
        await session.commit()


# ---------------------------------------------------------------------------
# POST /playbooks
# ---------------------------------------------------------------------------


async def test_create_playbook_returns_201_with_defaults(client):
    name = _unique("Create")
    playbook = await _create_playbook(
        client, name=name, department="IT", case_type="Softwareeinführung"
    )
    assert playbook["name"] == name
    assert playbook["version"] == "1.0"
    assert playbook["department"] == "IT"
    assert playbook["case_type"] == "Softwareeinführung"
    assert playbook["is_active"] is True
    assert playbook["content"]["checks"] == DEFAULT_CHECKS
    assert "id" in playbook and "created_at" in playbook


async def test_create_playbook_missing_content_returns_422(client):
    resp = await client.post(
        "/api/v1/playbooks", json={"name": _unique("Invalid"), "version": "1.0"}
    )
    assert resp.status_code == 422


async def test_create_playbook_empty_name_returns_422(client):
    resp = await client.post(
        "/api/v1/playbooks", json={"name": "", "version": "1.0", "content": {}}
    )
    assert resp.status_code == 422


async def test_create_playbook_content_must_be_object(client):
    resp = await client.post(
        "/api/v1/playbooks",
        json={"name": _unique("List"), "version": "1.0", "content": ["not", "dict"]},
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# GET /playbooks (list)
# ---------------------------------------------------------------------------


async def test_list_playbooks_contains_created(client):
    playbook = await _create_playbook(client)
    resp = await client.get("/api/v1/playbooks", params={"limit": 500})
    assert resp.status_code == 200
    ids = [p["id"] for p in resp.json()]
    assert playbook["id"] in ids


async def test_list_playbooks_orders_newest_first(client):
    older = await _create_playbook(client)
    newer = await _create_playbook(client)
    resp = await client.get("/api/v1/playbooks", params={"limit": 500})
    ids = [p["id"] for p in resp.json()]
    assert ids.index(newer["id"]) < ids.index(older["id"])


async def test_list_playbooks_is_active_filter(client):
    active = await _create_playbook(client)
    inactive = await _create_playbook(client)
    patch = await client.patch(
        f"/api/v1/playbooks/{inactive['id']}", json={"is_active": False}
    )
    assert patch.status_code == 200

    resp = await client.get(
        "/api/v1/playbooks", params={"is_active": "false", "limit": 500}
    )
    assert resp.status_code == 200
    inactive_ids = [p["id"] for p in resp.json()]
    assert inactive["id"] in inactive_ids
    assert active["id"] not in inactive_ids
    assert all(p["is_active"] is False for p in resp.json())

    resp = await client.get(
        "/api/v1/playbooks", params={"is_active": "true", "limit": 500}
    )
    active_ids = [p["id"] for p in resp.json()]
    assert active["id"] in active_ids
    assert inactive["id"] not in active_ids


async def test_list_playbooks_pagination(client):
    await _create_playbook(client)
    await _create_playbook(client)
    first = await client.get("/api/v1/playbooks", params={"skip": 0, "limit": 1})
    second = await client.get("/api/v1/playbooks", params={"skip": 1, "limit": 1})
    assert first.status_code == 200 and second.status_code == 200
    assert len(first.json()) == 1 and len(second.json()) == 1
    assert first.json()[0]["id"] != second.json()[0]["id"]


async def test_list_playbooks_rejects_out_of_range_params(client):
    assert (await client.get("/api/v1/playbooks?limit=0")).status_code == 422
    assert (await client.get("/api/v1/playbooks?limit=501")).status_code == 422
    assert (await client.get("/api/v1/playbooks?skip=-1")).status_code == 422


# ---------------------------------------------------------------------------
# GET /playbooks/{id}
# ---------------------------------------------------------------------------


async def test_get_playbook_by_id(client):
    playbook = await _create_playbook(client)
    resp = await client.get(f"/api/v1/playbooks/{playbook['id']}")
    assert resp.status_code == 200
    assert resp.json()["id"] == playbook["id"]
    assert resp.json()["name"] == playbook["name"]


async def test_get_playbook_not_found(client):
    resp = await client.get(f"/api/v1/playbooks/{NIL_UUID}")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Playbook not found"


async def test_get_playbook_invalid_uuid_returns_422(client):
    resp = await client.get("/api/v1/playbooks/not-a-uuid")
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# PATCH /playbooks/{id} + revisions
# ---------------------------------------------------------------------------


async def test_update_playbook_bumps_version_and_snapshots_revision(client):
    playbook = await _create_playbook(client)
    new_checks = DEFAULT_CHECKS + [
        {"name": "Löschfristen", "instruction": "Prüfe Löschfristen.", "scope": "case"}
    ]
    resp = await client.patch(
        f"/api/v1/playbooks/{playbook['id']}",
        json={"version": "2.0", "content": {"checks": new_checks}},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["version"] == "2.0"
    assert body["content"]["checks"] == new_checks
    assert body["name"] == playbook["name"]  # untouched fields stay

    revs = await client.get(f"/api/v1/playbooks/{playbook['id']}/revisions")
    assert revs.status_code == 200
    revisions = revs.json()
    assert len(revisions) == 1
    assert revisions[0]["playbook_id"] == playbook["id"]
    assert revisions[0]["version"] == "1.0"  # pre-update state
    assert revisions[0]["content"]["checks"] == DEFAULT_CHECKS
    assert revisions[0]["changed_by"]  # display name of the acting user


async def test_update_playbook_partial_fields(client):
    playbook = await _create_playbook(client, department="IT")
    resp = await client.patch(
        f"/api/v1/playbooks/{playbook['id']}",
        json={"name": _unique("Renamed"), "department": "HR", "case_type": "Audit"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["name"].startswith("Renamed-")
    assert resp.json()["department"] == "HR"
    assert resp.json()["case_type"] == "Audit"
    assert resp.json()["version"] == "1.0"
    assert resp.json()["content"] == playbook["content"]


async def test_update_playbook_not_found(client):
    resp = await client.patch(f"/api/v1/playbooks/{NIL_UUID}", json={"version": "9"})
    assert resp.status_code == 404


async def test_update_playbook_empty_name_returns_422(client):
    playbook = await _create_playbook(client)
    resp = await client.patch(f"/api/v1/playbooks/{playbook['id']}", json={"name": ""})
    assert resp.status_code == 422


async def test_revisions_newest_first_and_limit(client):
    playbook = await _create_playbook(client)
    for version in ("1.1", "1.2", "1.3"):
        resp = await client.patch(
            f"/api/v1/playbooks/{playbook['id']}", json={"version": version}
        )
        assert resp.status_code == 200

    resp = await client.get(f"/api/v1/playbooks/{playbook['id']}/revisions")
    assert resp.status_code == 200
    versions = [r["version"] for r in resp.json()]
    # snapshots hold the state *before* each PATCH
    assert versions == ["1.2", "1.1", "1.0"]

    limited = await client.get(
        f"/api/v1/playbooks/{playbook['id']}/revisions", params={"limit": 2}
    )
    assert [r["version"] for r in limited.json()] == ["1.2", "1.1"]


async def test_revisions_empty_for_fresh_playbook(client):
    playbook = await _create_playbook(client)
    resp = await client.get(f"/api/v1/playbooks/{playbook['id']}/revisions")
    assert resp.status_code == 200
    assert resp.json() == []


async def test_revisions_not_found(client):
    resp = await client.get(f"/api/v1/playbooks/{NIL_UUID}/revisions")
    assert resp.status_code == 404


async def test_revisions_limit_out_of_range_returns_422(client):
    playbook = await _create_playbook(client)
    resp = await client.get(
        f"/api/v1/playbooks/{playbook['id']}/revisions", params={"limit": 101}
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# POST /playbooks/{id}/revisions/{revision_id}/restore
# ---------------------------------------------------------------------------


async def test_restore_revision_reverts_content_and_snapshots_current(client):
    playbook = await _create_playbook(client)
    changed = {"checks": [{"name": "Neu", "instruction": "x", "scope": "document"}]}
    patch = await client.patch(
        f"/api/v1/playbooks/{playbook['id']}",
        json={"version": "2.0", "content": changed},
    )
    assert patch.status_code == 200

    revs = (await client.get(f"/api/v1/playbooks/{playbook['id']}/revisions")).json()
    original_revision = revs[0]
    assert original_revision["version"] == "1.0"

    resp = await client.post(
        f"/api/v1/playbooks/{playbook['id']}/revisions/{original_revision['id']}/restore"
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["version"] == "1.0"
    assert resp.json()["content"]["checks"] == DEFAULT_CHECKS

    current = await client.get(f"/api/v1/playbooks/{playbook['id']}")
    assert current.json()["version"] == "1.0"

    revs = (await client.get(f"/api/v1/playbooks/{playbook['id']}/revisions")).json()
    assert len(revs) == 2
    # newest snapshot captures the state that was replaced by the restore
    assert revs[0]["version"] == "2.0"
    assert revs[0]["content"] == changed
    assert revs[0]["changed_by"].endswith("(vor Wiederherstellung)")


async def test_restore_revision_unknown_playbook_returns_404(client):
    resp = await client.post(
        f"/api/v1/playbooks/{NIL_UUID}/revisions/{NIL_UUID}/restore"
    )
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Playbook not found"


async def test_restore_revision_unknown_revision_returns_404(client):
    playbook = await _create_playbook(client)
    resp = await client.post(
        f"/api/v1/playbooks/{playbook['id']}/revisions/{NIL_UUID}/restore"
    )
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Revision not found"


async def test_restore_revision_of_other_playbook_returns_404(client):
    """A revision id is only valid in combination with its own playbook."""
    first = await _create_playbook(client)
    second = await _create_playbook(client)
    await client.patch(f"/api/v1/playbooks/{first['id']}", json={"version": "1.1"})
    first_rev = (await client.get(f"/api/v1/playbooks/{first['id']}/revisions")).json()[
        0
    ]
    resp = await client.post(
        f"/api/v1/playbooks/{second['id']}/revisions/{first_rev['id']}/restore"
    )
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Revision not found"


# ---------------------------------------------------------------------------
# DELETE /playbooks/{id}
# ---------------------------------------------------------------------------


async def test_delete_playbook_removes_it_and_revisions(client):
    playbook = await _create_playbook(client)
    await client.patch(f"/api/v1/playbooks/{playbook['id']}", json={"version": "1.1"})

    resp = await client.delete(f"/api/v1/playbooks/{playbook['id']}")
    assert resp.status_code == 204
    assert (await client.get(f"/api/v1/playbooks/{playbook['id']}")).status_code == 404
    assert (
        await client.get(f"/api/v1/playbooks/{playbook['id']}/revisions")
    ).status_code == 404


async def test_delete_playbook_not_found(client):
    resp = await client.delete(f"/api/v1/playbooks/{NIL_UUID}")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /playbooks/for-selection
# ---------------------------------------------------------------------------


async def test_for_selection_requires_department(client):
    resp = await client.get("/api/v1/playbooks/for-selection")
    assert resp.status_code == 422
    resp = await client.get(
        "/api/v1/playbooks/for-selection", params={"department": ""}
    )
    assert resp.status_code == 422


async def test_for_selection_matches_department_and_ranks_priority(client):
    dept = _unique("Abteilung")
    other_dept = _unique("Andere")
    legacy = await _create_playbook(client, department=dept)  # priority 0
    prioritized = await _create_playbook(
        client,
        content={"checks": DEFAULT_CHECKS, "match": {"priority": 7}},
        department=dept,
    )
    foreign = await _create_playbook(client, department=other_dept)

    resp = await client.get(
        "/api/v1/playbooks/for-selection", params={"department": dept}
    )
    assert resp.status_code == 200
    by_id = {item["playbook"]["id"]: item for item in resp.json()}
    assert prioritized["id"] in by_id
    assert legacy["id"] in by_id
    assert foreign["id"] not in by_id
    assert by_id[prioritized["id"]]["match_priority"] == 7
    assert by_id[legacy["id"]]["match_priority"] == 0

    order = [item["playbook"]["id"] for item in resp.json()]
    assert order.index(prioritized["id"]) < order.index(legacy["id"])
    assert by_id[prioritized["id"]]["playbook"]["name"] == prioritized["name"]


async def test_for_selection_excludes_inactive_playbooks(client):
    dept = _unique("Inaktiv")
    playbook = await _create_playbook(client, department=dept)
    patch = await client.patch(
        f"/api/v1/playbooks/{playbook['id']}", json={"is_active": False}
    )
    assert patch.status_code == 200

    resp = await client.get(
        "/api/v1/playbooks/for-selection", params={"department": dept}
    )
    assert resp.status_code == 200
    assert playbook["id"] not in [item["playbook"]["id"] for item in resp.json()]


async def test_for_selection_strict_case_type_filter(client):
    dept = _unique("Strict")
    playbook = await _create_playbook(
        client,
        content={
            "checks": DEFAULT_CHECKS,
            "match": {"case_types": ["Softwareeinführung"], "priority": 3},
        },
        department=dept,
    )

    # Wizard mode (case type not chosen yet, strict=false): restriction is relaxed
    lenient = await client.get(
        "/api/v1/playbooks/for-selection", params={"department": dept}
    )
    assert playbook["id"] in [i["playbook"]["id"] for i in lenient.json()]

    # Missing case type with strict=true: playbooks requiring a case type drop out
    strict_none = await client.get(
        "/api/v1/playbooks/for-selection",
        params={"department": dept, "strict_case_type": "true"},
    )
    assert playbook["id"] not in [i["playbook"]["id"] for i in strict_none.json()]

    # A given, non-matching case type never matches (strict only affects "not chosen")
    lenient_miss = await client.get(
        "/api/v1/playbooks/for-selection",
        params={"department": dept, "case_type": "Audit"},
    )
    assert playbook["id"] not in [i["playbook"]["id"] for i in lenient_miss.json()]

    strict_miss = await client.get(
        "/api/v1/playbooks/for-selection",
        params={"department": dept, "case_type": "Audit", "strict_case_type": "true"},
    )
    assert playbook["id"] not in [i["playbook"]["id"] for i in strict_miss.json()]

    strict_hit = await client.get(
        "/api/v1/playbooks/for-selection",
        params={
            "department": dept,
            "case_type": "Softwareeinführung",
            "strict_case_type": "true",
        },
    )
    assert playbook["id"] in [i["playbook"]["id"] for i in strict_hit.json()]


async def test_for_selection_processing_context_filter(client):
    dept = _unique("Kontext")
    playbook = await _create_playbook(
        client,
        content={
            "checks": DEFAULT_CHECKS,
            "match": {"processing_contexts": ["Personalverwaltung"]},
        },
        department=dept,
    )
    without = await client.get(
        "/api/v1/playbooks/for-selection", params={"department": dept}
    )
    assert playbook["id"] not in [i["playbook"]["id"] for i in without.json()]

    with_ctx = await client.get(
        "/api/v1/playbooks/for-selection",
        params={"department": dept, "processing_context": "Personalverwaltung"},
    )
    assert playbook["id"] in [i["playbook"]["id"] for i in with_ctx.json()]


# ---------------------------------------------------------------------------
# GET /playbooks/{id}/coverage-preview
# ---------------------------------------------------------------------------

COVERAGE_CHECKS = [
    {
        "name": "VVT vollständig",
        "category": "VVT",
        "scope": "document",
        "document_types": ["vvt"],
        "instruction": "x",
    },
    {
        "name": "AVV vorhanden",
        "category": "AVV",
        "scope": "document",
        "document_types": ["avv"],
        "instruction": "x",
    },
    {
        "name": "Konsistenz über Dokumente",
        "category": "Konsistenz",
        "scope": "case",
        "document_types": ["vvt", "avv"],
        "instruction": "x",
    },
    {"name": "Allgemein", "instruction": "x"},  # no scope, no document_types
]


async def test_coverage_preview_unknown_playbook_returns_404(client):
    case = await create_case(client, title=_unique("Coverage"))
    resp = await client.get(
        f"/api/v1/playbooks/{NIL_UUID}/coverage-preview",
        params={"case_id": case["id"]},
    )
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Playbook not found"


async def test_coverage_preview_unknown_case_returns_404(client):
    playbook = await _create_playbook(client)
    resp = await client.get(
        f"/api/v1/playbooks/{playbook['id']}/coverage-preview",
        params={"case_id": NIL_UUID},
    )
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Case not found"


async def test_coverage_preview_requires_case_id(client):
    playbook = await _create_playbook(client)
    resp = await client.get(f"/api/v1/playbooks/{playbook['id']}/coverage-preview")
    assert resp.status_code == 422


async def test_coverage_preview_case_without_documents(client):
    playbook = await _create_playbook(client, checks=COVERAGE_CHECKS)
    case = await create_case(client, title=_unique("Coverage-leer"))
    resp = await client.get(
        f"/api/v1/playbooks/{playbook['id']}/coverage-preview",
        params={"case_id": case["id"]},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["playbook_id"] == playbook["id"]
    assert body["case_id"] == case["id"]
    assert body["total_checks"] == 4
    assert body["applicable_count"] == 2  # case-scoped + untyped
    assert body["missing_document_types"] == ["avv", "vvt"]

    by_name = {c["name"]: c for c in body["checks"]}
    assert by_name["VVT vollständig"]["applicable"] is False
    assert by_name["VVT vollständig"]["reason"] == "Fehlende Dokumenttypen: vvt"
    assert by_name["VVT vollständig"]["category"] == "VVT"
    assert by_name["AVV vorhanden"]["applicable"] is False
    assert by_name["Konsistenz über Dokumente"]["applicable"] is True
    assert by_name["Konsistenz über Dokumente"]["reason"] == "Vorgangsbezogen"
    assert by_name["Konsistenz über Dokumente"]["scope"] == "case"
    assert by_name["Allgemein"]["applicable"] is True
    assert by_name["Allgemein"]["reason"] == "Gilt für alle Dokumente"
    assert by_name["Allgemein"]["scope"] == "document"
    assert by_name["Allgemein"]["category"] == ""


async def test_coverage_preview_with_matching_document(client):
    playbook = await _create_playbook(client, checks=COVERAGE_CHECKS)
    case = await create_case(client, title=_unique("Coverage-vvt"))
    await _add_document(case["id"], "vvt")

    resp = await client.get(
        f"/api/v1/playbooks/{playbook['id']}/coverage-preview",
        params={"case_id": case["id"]},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["applicable_count"] == 3
    assert body["missing_document_types"] == ["avv"]
    by_name = {c["name"]: c for c in body["checks"]}
    assert by_name["VVT vollständig"]["applicable"] is True
    assert by_name["VVT vollständig"]["reason"] == "Passende Dokumente vorhanden: vvt"
    assert by_name["AVV vorhanden"]["applicable"] is False


async def test_coverage_preview_playbook_without_checks(client):
    playbook = await _create_playbook(client, checks=[])
    case = await create_case(client, title=_unique("Coverage-nochecks"))
    resp = await client.get(
        f"/api/v1/playbooks/{playbook['id']}/coverage-preview",
        params={"case_id": case["id"]},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_checks"] == 0
    assert body["applicable_count"] == 0
    assert body["checks"] == []
    assert body["missing_document_types"] == []
