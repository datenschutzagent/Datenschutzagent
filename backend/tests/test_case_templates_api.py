"""Integration tests for the /api/v1/case-templates routes.

Covers ``app/api/routes/case_templates.py``: creating, listing (with
``case_type``/``department`` filters), deleting templates and applying a
template to create a new case. Requires a live PostgreSQL (``DATABASE_URL``).
"""

from __future__ import annotations

import uuid
from typing import Any

import pytest

pytestmark = pytest.mark.asyncio

BASE = "/api/v1/case-templates"
UNKNOWN_ID = "00000000-0000-0000-0000-000000000000"


def _uniq(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


async def create_template(client, **overrides: Any) -> dict:
    payload: dict[str, Any] = {
        "name": _uniq("Vorlage"),
        "description": "Standardvorlage für Tests",
        "case_type": "Softwareeinführung",
        "department": "IT",
        "language": "de",
        "processing_context": "Einführung eines neuen Tools",
        "special_category_data": False,
        "international_transfer": False,
        **overrides,
    }
    resp = await client.post(BASE, json=payload)
    assert resp.status_code == 201, f"{BASE}: {resp.status_code} {resp.text}"
    return resp.json()


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------


async def test_create_template_returns_full_record(client):
    name = _uniq("HR-Onboarding")
    tpl = await create_template(
        client,
        name=name,
        case_type="Onboarding",
        department="HR",
        language="en",
        special_category_data=True,
        international_transfer=True,
    )
    assert tpl["id"]
    assert tpl["name"] == name
    assert tpl["description"] == "Standardvorlage für Tests"
    assert tpl["case_type"] == "Onboarding"
    assert tpl["department"] == "HR"
    assert tpl["language"] == "en"
    assert tpl["processing_context"] == "Einführung eines neuen Tools"
    assert tpl["special_category_data"] is True
    assert tpl["international_transfer"] is True
    assert tpl["is_builtin"] is False
    # created_by is the display name of the authenticated (default) user
    assert tpl["created_by"]
    assert tpl["created_at"] and tpl["updated_at"]


async def test_create_template_minimal_payload_uses_defaults(client):
    resp = await client.post(
        BASE, json={"name": _uniq("Minimal"), "case_type": "Sonstiges"}
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["description"] is None
    assert data["department"] is None
    assert data["language"] == "de"
    assert data["processing_context"] is None
    assert data["special_category_data"] is False
    assert data["international_transfer"] is False


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"name": "", "case_type": "X"},
        {"name": "Ohne Typ"},
        {"name": "Leerer Typ", "case_type": ""},
        {"name": "Bad Lang", "case_type": "X", "language": "fr"},
        {"name": "x" * 201, "case_type": "X"},
        {
            "name": "Zu langer Kontext",
            "case_type": "X",
            "processing_context": "y" * 501,
        },
    ],
)
async def test_create_template_invalid_payload_returns_422(client, payload):
    resp = await client.post(BASE, json=payload)
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# List + filters
# ---------------------------------------------------------------------------


async def test_list_templates_includes_created(client):
    tpl = await create_template(client)
    resp = await client.get(BASE)
    assert resp.status_code == 200
    ids = [t["id"] for t in resp.json()]
    assert tpl["id"] in ids


async def test_list_templates_filter_by_case_type_exact(client):
    case_type = _uniq("Typ")
    match = await create_template(client, case_type=case_type)
    other = await create_template(client, case_type=_uniq("Anderer"))

    resp = await client.get(BASE, params={"case_type": case_type})
    assert resp.status_code == 200
    data = resp.json()
    ids = {t["id"] for t in data}
    assert match["id"] in ids
    assert other["id"] not in ids
    assert all(t["case_type"] == case_type for t in data)

    # exact match only – a prefix does not match
    resp = await client.get(BASE, params={"case_type": case_type[:-3]})
    assert resp.status_code == 200
    assert match["id"] not in {t["id"] for t in resp.json()}


async def test_list_templates_filter_by_department_is_partial_and_case_insensitive(
    client,
):
    dept = _uniq("Fachbereich")
    match = await create_template(client, department=dept)
    other = await create_template(client, department=_uniq("Unrelated"))

    # substring, different case
    resp = await client.get(BASE, params={"department": dept[3:12].upper()})
    assert resp.status_code == 200
    ids = {t["id"] for t in resp.json()}
    assert match["id"] in ids
    assert other["id"] not in ids


async def test_list_templates_combined_filters(client):
    case_type = _uniq("Kombi")
    dept = _uniq("Dept")
    match = await create_template(client, case_type=case_type, department=dept)
    wrong_dept = await create_template(client, case_type=case_type, department="XYZ")
    wrong_type = await create_template(client, case_type="Other", department=dept)

    resp = await client.get(BASE, params={"case_type": case_type, "department": dept})
    assert resp.status_code == 200
    ids = {t["id"] for t in resp.json()}
    assert ids == {match["id"]}
    assert wrong_dept["id"] not in ids
    assert wrong_type["id"] not in ids


async def test_list_templates_no_match_returns_empty_list(client):
    resp = await client.get(BASE, params={"case_type": _uniq("NoSuchType")})
    assert resp.status_code == 200
    assert resp.json() == []


async def test_list_templates_sorted_builtin_first_then_name(client):
    from app.database import async_session_factory
    from app.models.db import CaseTemplateModel

    case_type = _uniq("Sort")
    # Custom templates with names in reverse alphabetical order
    zeta = await create_template(client, name=f"Zeta-{case_type}", case_type=case_type)
    alpha = await create_template(
        client, name=f"Alpha-{case_type}", case_type=case_type
    )
    builtin_id = uuid.uuid4()
    async with async_session_factory() as session:
        session.add(
            CaseTemplateModel(
                id=builtin_id,
                name=f"Zzz-Builtin-{case_type}",
                case_type=case_type,
                is_builtin=True,
                created_by="seed",
            )
        )
        await session.commit()

    resp = await client.get(BASE, params={"case_type": case_type})
    assert resp.status_code == 200
    ids = [t["id"] for t in resp.json()]
    assert ids == [str(builtin_id), alpha["id"], zeta["id"]]


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------


async def test_delete_template(client):
    tpl = await create_template(client)
    resp = await client.delete(f"{BASE}/{tpl['id']}")
    assert resp.status_code == 204

    listing = await client.get(BASE, params={"case_type": tpl["case_type"]})
    assert tpl["id"] not in {t["id"] for t in listing.json()}

    again = await client.delete(f"{BASE}/{tpl['id']}")
    assert again.status_code == 404


async def test_delete_template_unknown_returns_404(client):
    resp = await client.delete(f"{BASE}/{UNKNOWN_ID}")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Vorlage nicht gefunden"


async def test_delete_template_invalid_uuid_returns_422(client):
    resp = await client.delete(f"{BASE}/not-a-uuid")
    assert resp.status_code == 422


async def test_delete_builtin_template_returns_403(client):
    from app.database import async_session_factory
    from app.models.db import CaseTemplateModel

    builtin_id = uuid.uuid4()
    async with async_session_factory() as session:
        session.add(
            CaseTemplateModel(
                id=builtin_id,
                name=_uniq("Builtin"),
                case_type="Sonstiges",
                is_builtin=True,
                created_by="seed",
            )
        )
        await session.commit()

    resp = await client.delete(f"{BASE}/{builtin_id}")
    assert resp.status_code == 403
    assert "Eingebaute Vorlagen" in resp.json()["detail"]

    # still present afterwards
    listing = await client.get(BASE)
    assert str(builtin_id) in {t["id"] for t in listing.json()}


# ---------------------------------------------------------------------------
# Apply
# ---------------------------------------------------------------------------


async def test_apply_template_unknown_template_returns_404(client):
    resp = await client.post(
        f"{BASE}/apply", json={"template_id": UNKNOWN_ID, "title": "Egal"}
    )
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Vorlage nicht gefunden"


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"title": "Nur Titel"},
        {"template_id": UNKNOWN_ID},
        {"template_id": UNKNOWN_ID, "title": ""},
        {"template_id": "not-a-uuid", "title": "x"},
        {"template_id": UNKNOWN_ID, "title": "x", "deadline": "31.03.2027"},
        {"template_id": UNKNOWN_ID, "title": "x", "assignee": "a" * 201},
    ],
)
async def test_apply_template_invalid_payload_returns_422(client, payload):
    resp = await client.post(f"{BASE}/apply", json=payload)
    assert resp.status_code == 422


async def test_apply_deleted_template_returns_404(client):
    tpl = await create_template(client)
    assert (await client.delete(f"{BASE}/{tpl['id']}")).status_code == 204
    resp = await client.post(
        f"{BASE}/apply", json={"template_id": tpl["id"], "title": "Nach Löschung"}
    )
    assert resp.status_code == 404


async def test_apply_template_creates_case_with_template_defaults(client):
    """Regression: apply used to 500 (MissingGreenlet) because CaseResponse touched
    the expired documents/findings relationships after refresh()."""
    tpl = (
        await client.post(
            "/api/v1/case-templates",
            json={
                "name": f"Vorlage {uuid.uuid4().hex[:8]}",
                "case_type": "Softwareeinführung",
                "department": "IT",
                "language": "de",
                "processing_context": "Aus Vorlage",
                "special_category_data": True,
                "international_transfer": False,
            },
        )
    ).json()
    resp = await client.post(
        "/api/v1/case-templates/apply",
        json={
            "template_id": tpl["id"],
            "title": "Aus Vorlage angelegt",
            "assignee": "DSB",
        },
    )
    assert resp.status_code == 201, resp.text
    case = resp.json()
    assert case["title"] == "Aus Vorlage angelegt"
    assert case["case_type"] == "Softwareeinführung"
    assert case["department"] == "IT"
    assert case["special_category_data"] is True
    assert case["processing_context"] == "Aus Vorlage"
    assert case["documents"] == [] and case["findings"] == []
