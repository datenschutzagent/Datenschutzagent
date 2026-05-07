"""Integration tests for the vorgangsspezifische Datenschutzerklaerungs-API.

Tested behaviour:
- Generation requires a valid case_id (404 otherwise)
- Each generation increments the per-case version
- Cascade delete: deleting a case removes its policies
- Global list endpoint returns all stored policies (read-only overview)
"""
import pytest


pytestmark = pytest.mark.asyncio


class _FakeLLMResult:
    """Lokaler Stand-in fuer ein pydantic_ai RunResult (vermeidet Import aus conftest)."""

    def __init__(self, output=None):
        self.output = output
        self.data = output


async def _create_case(client, **overrides) -> dict:
    payload = {
        "title": "Test-Vorgang Datenschutzerklaerung",
        "department": "IT",
        "case_type": "Softwareeinfuehrung",
        "language": "de",
        "created_by": "test@example.com",
        "assignee": "DSB Team",
        "processing_context": None,
        "special_category_data": False,
        "international_transfer": False,
        **overrides,
    }
    resp = await client.post("/api/v1/cases", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


def _llm_result(version_note: str = "Initial") -> _FakeLLMResult:
    """Erzeugt ein Fake-LLM-Ergebnis im erwarteten Pydantic-Format."""
    from app.services.privacy_policy_service import _PrivacyPolicyLLMResult

    return _FakeLLMResult(
        _PrivacyPolicyLLMResult(
            title="Datenschutzerklaerung Testvorgang",
            content_markdown="# Datenschutzerklaerung\n\nInhalt …",
            version_note=version_note,
        )
    )


async def test_generate_requires_valid_case(client, mock_llm):
    mock_llm.run.return_value = _llm_result()
    resp = await client.post(
        "/api/v1/cases/00000000-0000-0000-0000-000000000000/privacy-policies/generate",
        json={},
    )
    assert resp.status_code == 404


async def test_generate_creates_first_version(client, mock_llm):
    case = await _create_case(client, title="Neue Verarbeitung A")
    mock_llm.run.return_value = _llm_result(version_note="v1")

    resp = await client.post(
        f"/api/v1/cases/{case['id']}/privacy-policies/generate",
        json={"contact": "DSB GmbH, Musterweg 1", "notes": "Cookie-Banner aktiv"},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["case_id"] == case["id"]
    assert body["version"] == 1
    assert body["title"] == "Datenschutzerklaerung Testvorgang"
    assert "Datenschutzerklaerung" in body["content_markdown"]


async def test_generate_increments_version(client, mock_llm):
    case = await _create_case(client, title="Neue Verarbeitung B")

    mock_llm.run.return_value = _llm_result("v1")
    r1 = await client.post(
        f"/api/v1/cases/{case['id']}/privacy-policies/generate", json={}
    )
    assert r1.status_code == 201
    assert r1.json()["version"] == 1

    mock_llm.run.return_value = _llm_result("v2")
    r2 = await client.post(
        f"/api/v1/cases/{case['id']}/privacy-policies/generate", json={}
    )
    assert r2.status_code == 201
    assert r2.json()["version"] == 2


async def test_list_versions_for_case(client, mock_llm):
    case = await _create_case(client, title="Neue Verarbeitung C")
    mock_llm.run.return_value = _llm_result()
    await client.post(f"/api/v1/cases/{case['id']}/privacy-policies/generate", json={})
    mock_llm.run.return_value = _llm_result()
    await client.post(f"/api/v1/cases/{case['id']}/privacy-policies/generate", json={})

    resp = await client.get(f"/api/v1/cases/{case['id']}/privacy-policies")
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 2
    # neueste zuerst
    assert items[0]["version"] == 2
    assert items[1]["version"] == 1


async def test_global_list_includes_policy(client, mock_llm):
    case = await _create_case(client, title="Neue Verarbeitung D")
    mock_llm.run.return_value = _llm_result()
    create = await client.post(
        f"/api/v1/cases/{case['id']}/privacy-policies/generate", json={}
    )
    policy_id = create.json()["id"]

    resp = await client.get("/api/v1/privacy-policies")
    assert resp.status_code == 200
    ids = [p["id"] for p in resp.json()]
    assert policy_id in ids


async def test_update_policy(client, mock_llm):
    case = await _create_case(client, title="Neue Verarbeitung E")
    mock_llm.run.return_value = _llm_result()
    create = await client.post(
        f"/api/v1/cases/{case['id']}/privacy-policies/generate", json={}
    )
    policy_id = create.json()["id"]

    resp = await client.patch(
        f"/api/v1/privacy-policies/{policy_id}",
        json={"title": "Neuer Titel", "content_markdown": "# Geaendert"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["title"] == "Neuer Titel"
    assert body["content_markdown"] == "# Geaendert"


async def test_cascade_delete_on_case(client, mock_llm):
    case = await _create_case(client, title="Neue Verarbeitung F")
    mock_llm.run.return_value = _llm_result()
    create = await client.post(
        f"/api/v1/cases/{case['id']}/privacy-policies/generate", json={}
    )
    policy_id = create.json()["id"]

    # Case loeschen → privacy_policies haengen via ON DELETE CASCADE mit
    del_resp = await client.delete(f"/api/v1/cases/{case['id']}")
    assert del_resp.status_code == 204

    # Policy darf nicht mehr abrufbar sein
    get_resp = await client.get(f"/api/v1/privacy-policies/{policy_id}")
    assert get_resp.status_code == 404


async def test_list_for_unknown_case_returns_404(client):
    resp = await client.get("/api/v1/cases/00000000-0000-0000-0000-000000000000/privacy-policies")
    assert resp.status_code == 404
