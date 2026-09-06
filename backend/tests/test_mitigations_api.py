"""Integration tests for the mitigation catalog and link routes.

Covers ``app/api/routes/mitigations.py``: the catalog endpoint, linking and
unlinking catalog mitigations to cases (DSFA side) and AVV contracts, and the
inherent-vs-residual ``risk-delta`` views. Requires a live PostgreSQL
(``DATABASE_URL``); the mitigation catalog comes from the default org profile
(``app/data/org_profiles/default/risk_config.yaml``).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest

from tests.factories import create_avv, create_case, create_tom

pytestmark = pytest.mark.asyncio

UNKNOWN_ID = "00000000-0000-0000-0000-000000000000"

# Catalog ids from the default risk_config.yaml, grouped by ``applies_to``.
BOTH_ID = "encryption_at_rest"
BOTH_ID_2 = "audit_logging"
DSFA_ONLY_ID = "pseudonymization"
AVV_ONLY_ID = "dpa_signed_eu_scc"


def _uniq(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


# ---------------------------------------------------------------------------
# Catalog
# ---------------------------------------------------------------------------


async def test_catalog_lists_default_entries(client):
    resp = await client.get("/api/v1/mitigations/catalog")
    assert resp.status_code == 200
    data = resp.json()
    assert data["enabled"] is True
    assert data["min_likelihood"] >= 1
    assert data["min_severity"] >= 1
    assert data["min_avv_score"] >= 1.0
    ids = {entry["id"] for entry in data["catalog"]}
    assert {BOTH_ID, DSFA_ONLY_ID, AVV_ONLY_ID} <= ids


async def test_catalog_entry_shape(client):
    resp = await client.get("/api/v1/mitigations/catalog")
    entries = {e["id"]: e for e in resp.json()["catalog"]}
    entry = entries[BOTH_ID]
    assert entry["applies_to"] == "both"
    assert entry["label"]
    assert isinstance(entry["evidence_required"], bool)
    reduction = entry["reduction"]
    assert set(reduction) >= {
        "score_delta",
        "dimension_deltas",
        "likelihood_delta",
        "severity_delta",
        "applicable_risk_keywords",
    }
    assert isinstance(reduction["dimension_deltas"], dict)
    assert isinstance(reduction["applicable_risk_keywords"], list)
    assert entries[DSFA_ONLY_ID]["applies_to"] == "dsfa"
    assert entries[AVV_ONLY_ID]["applies_to"] == "avv"


# ---------------------------------------------------------------------------
# Case <-> mitigation
# ---------------------------------------------------------------------------


async def test_list_case_mitigations_empty_for_new_case(client):
    case = await create_case(client, title=_uniq("Mitigation-Case"))
    resp = await client.get(f"/api/v1/cases/{case['id']}/mitigations")
    assert resp.status_code == 200
    assert resp.json() == []


async def test_list_case_mitigations_unknown_case_returns_404(client):
    resp = await client.get(f"/api/v1/cases/{UNKNOWN_ID}/mitigations")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Vorgang nicht gefunden"


async def test_link_case_mitigation_success(client):
    case = await create_case(client, title=_uniq("Mitigation-Link"))
    resp = await client.post(
        f"/api/v1/cases/{case['id']}/mitigations",
        json={"mitigation_id": BOTH_ID, "notes": "AES-256 auf allen Volumes"},
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["case_id"] == case["id"]
    assert data["mitigation_id"] == BOTH_ID
    assert data["notes"] == "AES-256 auf allen Volumes"
    assert data["tom_id"] is None
    assert data["evidence_doc_id"] is None
    assert data["applied_by"]  # derived from the authenticated user
    assert data["applied_at"]
    assert data["catalog_entry"]["id"] == BOTH_ID
    assert data["catalog_entry"]["applies_to"] == "both"


async def test_link_case_mitigation_with_tom_reference(client):
    case = await create_case(client, title=_uniq("Mitigation-TOM"))
    tom = await create_tom(client, title=_uniq("TOM"))
    resp = await client.post(
        f"/api/v1/cases/{case['id']}/mitigations",
        json={"mitigation_id": DSFA_ONLY_ID, "tom_id": tom["id"]},
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["tom_id"] == tom["id"]
    assert data["catalog_entry"]["applies_to"] == "dsfa"


async def test_list_case_mitigations_after_link_orders_by_applied_at(client):
    case = await create_case(client, title=_uniq("Mitigation-List"))
    for mid in (BOTH_ID, BOTH_ID_2):
        resp = await client.post(
            f"/api/v1/cases/{case['id']}/mitigations", json={"mitigation_id": mid}
        )
        assert resp.status_code == 201, resp.text

    resp = await client.get(f"/api/v1/cases/{case['id']}/mitigations")
    assert resp.status_code == 200
    data = resp.json()
    assert [row["mitigation_id"] for row in data] == [BOTH_ID, BOTH_ID_2]
    assert all(row["catalog_entry"]["id"] == row["mitigation_id"] for row in data)


async def test_list_case_mitigations_without_catalog_entry(client):
    """A link whose catalog id was removed from the YAML still lists (entry=None)."""
    from app.database import async_session_factory
    from app.models.db import CaseMitigationLinkModel

    case = await create_case(client, title=_uniq("Mitigation-Orphan"))
    orphan_id = _uniq("removed_mitigation")
    async with async_session_factory() as session:
        session.add(
            CaseMitigationLinkModel(
                case_id=uuid.UUID(case["id"]),
                mitigation_id=orphan_id,
                applied_by="test",
            )
        )
        await session.commit()

    resp = await client.get(f"/api/v1/cases/{case['id']}/mitigations")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["mitigation_id"] == orphan_id
    assert data[0]["catalog_entry"] is None


async def test_link_case_mitigation_duplicate_returns_409(client):
    case = await create_case(client, title=_uniq("Mitigation-Dup"))
    first = await client.post(
        f"/api/v1/cases/{case['id']}/mitigations", json={"mitigation_id": BOTH_ID}
    )
    assert first.status_code == 201
    second = await client.post(
        f"/api/v1/cases/{case['id']}/mitigations", json={"mitigation_id": BOTH_ID}
    )
    assert second.status_code == 409
    assert "bereits verknüpft" in second.json()["detail"]


async def test_link_case_mitigation_unknown_catalog_id_returns_404(client):
    case = await create_case(client, title=_uniq("Mitigation-Unknown"))
    resp = await client.post(
        f"/api/v1/cases/{case['id']}/mitigations",
        json={"mitigation_id": "does_not_exist"},
    )
    assert resp.status_code == 404
    assert "nicht im Katalog" in resp.json()["detail"]


async def test_link_case_mitigation_avv_only_entry_returns_422(client):
    case = await create_case(client, title=_uniq("Mitigation-AvvOnly"))
    resp = await client.post(
        f"/api/v1/cases/{case['id']}/mitigations", json={"mitigation_id": AVV_ONLY_ID}
    )
    assert resp.status_code == 422
    assert "nicht auf DSFA anwendbar" in resp.json()["detail"]


async def test_link_case_mitigation_unknown_case_returns_404(client):
    resp = await client.post(
        f"/api/v1/cases/{UNKNOWN_ID}/mitigations", json={"mitigation_id": BOTH_ID}
    )
    assert resp.status_code == 404


async def test_link_case_mitigation_invalid_payload_returns_422(client):
    case = await create_case(client, title=_uniq("Mitigation-Invalid"))
    empty_id = await client.post(
        f"/api/v1/cases/{case['id']}/mitigations", json={"mitigation_id": ""}
    )
    assert empty_id.status_code == 422
    missing = await client.post(f"/api/v1/cases/{case['id']}/mitigations", json={})
    assert missing.status_code == 422
    bad_tom = await client.post(
        f"/api/v1/cases/{case['id']}/mitigations",
        json={"mitigation_id": BOTH_ID, "tom_id": "not-a-uuid"},
    )
    assert bad_tom.status_code == 422


async def test_link_case_mitigation_invalid_case_uuid_returns_422(client):
    resp = await client.post(
        "/api/v1/cases/not-a-uuid/mitigations", json={"mitigation_id": BOTH_ID}
    )
    assert resp.status_code == 422


async def test_unlink_case_mitigation(client):
    case = await create_case(client, title=_uniq("Mitigation-Unlink"))
    link = await client.post(
        f"/api/v1/cases/{case['id']}/mitigations", json={"mitigation_id": BOTH_ID}
    )
    assert link.status_code == 201

    resp = await client.delete(f"/api/v1/cases/{case['id']}/mitigations/{BOTH_ID}")
    assert resp.status_code == 204

    listing = await client.get(f"/api/v1/cases/{case['id']}/mitigations")
    assert listing.json() == []

    # Re-linking works again once the old link is gone.
    again = await client.post(
        f"/api/v1/cases/{case['id']}/mitigations", json={"mitigation_id": BOTH_ID}
    )
    assert again.status_code == 201


async def test_unlink_case_mitigation_not_linked_returns_404(client):
    case = await create_case(client, title=_uniq("Mitigation-Unlink404"))
    resp = await client.delete(f"/api/v1/cases/{case['id']}/mitigations/{BOTH_ID}")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Verknüpfung nicht gefunden"


async def test_unlink_case_mitigation_unknown_case_returns_404(client):
    resp = await client.delete(f"/api/v1/cases/{UNKNOWN_ID}/mitigations/{BOTH_ID}")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Case risk-delta (DSFA)
# ---------------------------------------------------------------------------


async def test_case_risk_delta_without_dsfa_returns_404(client):
    case = await create_case(client, title=_uniq("RiskDelta-NoDSFA"))
    resp = await client.get(f"/api/v1/cases/{case['id']}/risk-delta")
    assert resp.status_code == 404
    assert "Keine DSFA" in resp.json()["detail"]


async def test_case_risk_delta_unknown_case_returns_404(client):
    resp = await client.get(f"/api/v1/cases/{UNKNOWN_ID}/risk-delta")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Vorgang nicht gefunden"


async def _seed_dsfa(case_id: str, payload: dict) -> None:
    from app.database import async_session_factory
    from app.models.db import DSFAAssessmentModel

    async with async_session_factory() as session:
        session.add(
            DSFAAssessmentModel(
                case_id=uuid.UUID(case_id),
                status="draft",
                payload=payload,
                generated_at=datetime.now(UTC),
            )
        )
        await session.commit()


async def test_case_risk_delta_with_empty_payload_returns_404(client):
    case = await create_case(client, title=_uniq("RiskDelta-Empty"))
    await _seed_dsfa(case["id"], {})
    resp = await client.get(f"/api/v1/cases/{case['id']}/risk-delta")
    assert resp.status_code == 404


async def test_case_risk_delta_from_persisted_dsfa(client):
    case = await create_case(client, title=_uniq("RiskDelta-DSFA"))
    await _seed_dsfa(
        case["id"],
        {
            "residual_risk": "medium",
            "inherent_residual_risk": "high",
            "applied_mitigations": [BOTH_ID, DSFA_ONLY_ID],
            "applied_effects": [{"mitigation_id": BOTH_ID, "likelihood_delta": -1}],
        },
    )
    resp = await client.get(f"/api/v1/cases/{case['id']}/risk-delta")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["target_type"] == "dsfa"
    assert data["target_id"] == case["id"]
    assert data["inherent"] == {"risk_score": None, "risk_level": "high"}
    assert data["residual"] == {"risk_score": None, "risk_level": "medium"}
    assert data["applied_mitigations"] == [BOTH_ID, DSFA_ONLY_ID]
    assert data["applied_effects"] == [
        {"mitigation_id": BOTH_ID, "likelihood_delta": -1}
    ]
    assert data["assessed_at"]


async def test_case_risk_delta_falls_back_to_residual_when_no_inherent(client):
    """Legacy DSFA payloads without ``inherent_residual_risk`` reuse residual."""
    case = await create_case(client, title=_uniq("RiskDelta-Legacy"))
    await _seed_dsfa(case["id"], {"residual_risk": "low"})
    resp = await client.get(f"/api/v1/cases/{case['id']}/risk-delta")
    assert resp.status_code == 200
    data = resp.json()
    assert data["inherent"]["risk_level"] == "low"
    assert data["residual"]["risk_level"] == "low"
    assert data["applied_mitigations"] == []
    assert data["applied_effects"] == []


# ---------------------------------------------------------------------------
# AVV <-> mitigation
# ---------------------------------------------------------------------------


async def test_list_avv_mitigations_empty_for_new_contract(client):
    avv = await create_avv(client, partner_name=_uniq("Mitigation-AVV"))
    resp = await client.get(f"/api/v1/avv/{avv['id']}/mitigations")
    assert resp.status_code == 200
    assert resp.json() == []


async def test_list_avv_mitigations_unknown_contract_returns_404(client):
    resp = await client.get(f"/api/v1/avv/{UNKNOWN_ID}/mitigations")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "AVV nicht gefunden"


async def test_link_avv_mitigation_success(client):
    avv = await create_avv(client, partner_name=_uniq("Mitigation-AVV-Link"))
    tom = await create_tom(client, title=_uniq("TOM-AVV"))
    resp = await client.post(
        f"/api/v1/avv/{avv['id']}/mitigations",
        json={"mitigation_id": AVV_ONLY_ID, "tom_id": tom["id"], "notes": "SCC 2021"},
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["avv_contract_id"] == avv["id"]
    assert data["mitigation_id"] == AVV_ONLY_ID
    assert data["tom_id"] == tom["id"]
    assert data["notes"] == "SCC 2021"
    assert data["applied_by"]
    assert data["catalog_entry"]["applies_to"] == "avv"
    # AVV links carry no evidence_doc_id column.
    assert "evidence_doc_id" not in data


async def test_link_avv_mitigation_both_entry_allowed(client):
    avv = await create_avv(client, partner_name=_uniq("Mitigation-AVV-Both"))
    resp = await client.post(
        f"/api/v1/avv/{avv['id']}/mitigations", json={"mitigation_id": BOTH_ID}
    )
    assert resp.status_code == 201
    assert resp.json()["catalog_entry"]["applies_to"] == "both"


async def test_list_avv_mitigations_after_link(client):
    avv = await create_avv(client, partner_name=_uniq("Mitigation-AVV-List"))
    for mid in (BOTH_ID, AVV_ONLY_ID):
        resp = await client.post(
            f"/api/v1/avv/{avv['id']}/mitigations", json={"mitigation_id": mid}
        )
        assert resp.status_code == 201, resp.text
    resp = await client.get(f"/api/v1/avv/{avv['id']}/mitigations")
    assert resp.status_code == 200
    data = resp.json()
    assert [row["mitigation_id"] for row in data] == [BOTH_ID, AVV_ONLY_ID]
    assert all(row["catalog_entry"] is not None for row in data)


async def test_list_avv_mitigations_without_catalog_entry(client):
    from app.database import async_session_factory
    from app.models.db import AvvMitigationLinkModel

    avv = await create_avv(client, partner_name=_uniq("Mitigation-AVV-Orphan"))
    orphan_id = _uniq("removed_mitigation")
    async with async_session_factory() as session:
        session.add(
            AvvMitigationLinkModel(
                avv_contract_id=uuid.UUID(avv["id"]),
                mitigation_id=orphan_id,
                applied_by="test",
            )
        )
        await session.commit()

    resp = await client.get(f"/api/v1/avv/{avv['id']}/mitigations")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["mitigation_id"] == orphan_id
    assert data[0]["catalog_entry"] is None


async def test_link_avv_mitigation_duplicate_returns_409(client):
    avv = await create_avv(client, partner_name=_uniq("Mitigation-AVV-Dup"))
    first = await client.post(
        f"/api/v1/avv/{avv['id']}/mitigations", json={"mitigation_id": BOTH_ID}
    )
    assert first.status_code == 201
    second = await client.post(
        f"/api/v1/avv/{avv['id']}/mitigations", json={"mitigation_id": BOTH_ID}
    )
    assert second.status_code == 409


async def test_link_avv_mitigation_unknown_catalog_id_returns_404(client):
    avv = await create_avv(client, partner_name=_uniq("Mitigation-AVV-Unknown"))
    resp = await client.post(
        f"/api/v1/avv/{avv['id']}/mitigations", json={"mitigation_id": "nope"}
    )
    assert resp.status_code == 404
    assert "nicht im Katalog" in resp.json()["detail"]


async def test_link_avv_mitigation_dsfa_only_entry_returns_422(client):
    avv = await create_avv(client, partner_name=_uniq("Mitigation-AVV-DsfaOnly"))
    resp = await client.post(
        f"/api/v1/avv/{avv['id']}/mitigations", json={"mitigation_id": DSFA_ONLY_ID}
    )
    assert resp.status_code == 422
    assert "nicht auf AVV anwendbar" in resp.json()["detail"]


async def test_link_avv_mitigation_unknown_contract_returns_404(client):
    resp = await client.post(
        f"/api/v1/avv/{UNKNOWN_ID}/mitigations", json={"mitigation_id": BOTH_ID}
    )
    assert resp.status_code == 404


async def test_link_avv_mitigation_invalid_payload_returns_422(client):
    avv = await create_avv(client, partner_name=_uniq("Mitigation-AVV-Invalid"))
    resp = await client.post(
        f"/api/v1/avv/{avv['id']}/mitigations", json={"mitigation_id": "x" * 81}
    )
    assert resp.status_code == 422


async def test_unlink_avv_mitigation(client):
    avv = await create_avv(client, partner_name=_uniq("Mitigation-AVV-Unlink"))
    link = await client.post(
        f"/api/v1/avv/{avv['id']}/mitigations", json={"mitigation_id": AVV_ONLY_ID}
    )
    assert link.status_code == 201

    resp = await client.delete(f"/api/v1/avv/{avv['id']}/mitigations/{AVV_ONLY_ID}")
    assert resp.status_code == 204

    listing = await client.get(f"/api/v1/avv/{avv['id']}/mitigations")
    assert listing.json() == []


async def test_unlink_avv_mitigation_not_linked_returns_404(client):
    avv = await create_avv(client, partner_name=_uniq("Mitigation-AVV-Unlink404"))
    resp = await client.delete(f"/api/v1/avv/{avv['id']}/mitigations/{BOTH_ID}")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Verknüpfung nicht gefunden"


# ---------------------------------------------------------------------------
# AVV risk-delta
# ---------------------------------------------------------------------------


async def test_avv_risk_delta_without_assessment_returns_404(client):
    avv = await create_avv(client, partner_name=_uniq("RiskDelta-AVV-None"))
    resp = await client.get(f"/api/v1/avv/{avv['id']}/risk-delta")
    assert resp.status_code == 404
    assert "Keine Risikobewertung" in resp.json()["detail"]


async def test_avv_risk_delta_unknown_contract_returns_404(client):
    resp = await client.get(f"/api/v1/avv/{UNKNOWN_ID}/risk-delta")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "AVV nicht gefunden"


async def _seed_avv_assessment(contract_id: str, **fields) -> None:
    from sqlalchemy import select

    from app.database import async_session_factory
    from app.models.db import AVVContractModel

    async with async_session_factory() as session:
        contract = (
            await session.execute(
                select(AVVContractModel).where(
                    AVVContractModel.id == uuid.UUID(contract_id)
                )
            )
        ).scalar_one()
        for key, value in fields.items():
            setattr(contract, key, value)
        await session.commit()


async def test_avv_risk_delta_from_persisted_assessment(client):
    avv = await create_avv(client, partner_name=_uniq("RiskDelta-AVV"))
    await _seed_avv_assessment(
        avv["id"],
        risk_assessed_at=datetime.now(UTC),
        inherent_risk_score=72,
        inherent_risk_level="high",
        risk_score=48,
        risk_level="medium",
        risk_assessment={
            "applied_mitigations": [AVV_ONLY_ID],
            "applied_effects": [{"mitigation_id": AVV_ONLY_ID, "score_delta": -24}],
        },
    )
    resp = await client.get(f"/api/v1/avv/{avv['id']}/risk-delta")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["target_type"] == "avv"
    assert data["target_id"] == avv["id"]
    assert data["inherent"] == {"risk_score": 72, "risk_level": "high"}
    assert data["residual"] == {"risk_score": 48, "risk_level": "medium"}
    assert data["applied_mitigations"] == [AVV_ONLY_ID]
    assert data["applied_effects"][0]["mitigation_id"] == AVV_ONLY_ID
    assert data["assessed_at"]


async def test_avv_risk_delta_with_assessment_but_no_details(client):
    """``risk_assessment`` may be NULL even when an assessment timestamp exists."""
    avv = await create_avv(client, partner_name=_uniq("RiskDelta-AVV-Bare"))
    await _seed_avv_assessment(
        avv["id"],
        risk_assessed_at=datetime.now(UTC),
        risk_score=30,
        risk_level="low",
        risk_assessment=None,
    )
    resp = await client.get(f"/api/v1/avv/{avv['id']}/risk-delta")
    assert resp.status_code == 200
    data = resp.json()
    assert data["inherent"] == {"risk_score": None, "risk_level": None}
    assert data["residual"] == {"risk_score": 30, "risk_level": "low"}
    assert data["applied_mitigations"] == []
    assert data["applied_effects"] == []
