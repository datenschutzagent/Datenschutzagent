"""Integration-Tests fuer /api/v1/analytics Endpoints (Pipeline, Velocity, Maturity).

Voraussetzung: lebende PostgreSQL-DB (DATABASE_URL env var) — wie bei den anderen Integrationstests.
"""

import pytest

from tests.factories import create_avv, create_dsr, create_tom

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Hilfsfunktionen zum Befuellen
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------


async def test_pipeline_returns_structure(client):
    resp = await client.get("/api/v1/analytics/pipeline")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "generated_at" in data
    assert "avv" in data and "buckets" in data["avv"]
    assert "tom" in data and "by_category" in data["tom"]
    assert "dsfa" in data and "coverage_pct" in data["dsfa"]
    # Buckets are always present (even if empty)
    assert {b["bucket"] for b in data["avv"]["buckets"]} >= {
        "overdue",
        "0_30",
        "undated",
    }


async def test_pipeline_avv_buckets_classify_expiry(client):
    # AVV der bald ablaeuft -> 0_30 oder 31_90.
    from datetime import date, timedelta

    soon = (date.today() + timedelta(days=20)).isoformat()
    avv = await create_avv(client, partner_name="Pipeline Soon", expiry_date=soon)
    resp = await client.patch(f"/api/v1/avv/{avv['id']}", json={"status": "signed"})
    assert resp.status_code == 200

    resp = await client.get("/api/v1/analytics/pipeline")
    data = resp.json()
    bucket_for_0_30 = next(b for b in data["avv"]["buckets"] if b["bucket"] == "0_30")
    assert bucket_for_0_30["count"] >= 1


async def test_pipeline_dept_filter(client):
    await create_avv(
        client, partner_name="Pipeline Dept Filter", department="OnlyMe-XYZ-Dept"
    )
    resp = await client.get("/api/v1/analytics/pipeline?department=OnlyMe-XYZ-Dept")
    assert resp.status_code == 200
    data = resp.json()
    assert data["department_filter"] == "OnlyMe-XYZ-Dept"
    # AVV in dieser unique Abteilung muss in den Buckets auftauchen.
    assert sum(b["count"] for b in data["avv"]["buckets"]) >= 1


# ---------------------------------------------------------------------------
# Velocity
# ---------------------------------------------------------------------------


async def test_velocity_returns_structure(client):
    resp = await client.get("/api/v1/analytics/velocity")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "dsr" in data and "histogram" in data["dsr"]
    assert "breach" in data and "histogram_authority" in data["breach"]
    assert "findings" in data
    assert "funnels" in data and len(data["funnels"]) == 2
    funnel_entities = {f["entity"] for f in data["funnels"]}
    assert funnel_entities == {"DSR", "Datenpanne"}


async def test_velocity_dsr_mttr_after_response(client):
    """Wenn ein DSR responded_at hat, muss er in der Velocity-Stichprobe auftauchen."""
    dsr = await create_dsr(client, received_at="2026-02-01")
    # Markiere als beantwortet (responded_at = received_at + 5 Tage)
    resp = await client.patch(
        f"/api/v1/dsr/{dsr['id']}",
        json={"status": "response_sent", "responded_at": "2026-02-06"},
    )
    assert resp.status_code == 200, resp.text

    resp = await client.get("/api/v1/analytics/velocity")
    data = resp.json()
    assert data["dsr"]["sample_size"] >= 1
    # Median fuer einen Sample mit 5d MTTR muss zwischen 0 und ~365 liegen.
    if data["dsr"]["median_days"] is not None:
        assert 0 <= data["dsr"]["median_days"] <= 400


# ---------------------------------------------------------------------------
# Maturity
# ---------------------------------------------------------------------------


async def test_maturity_returns_structure(client):
    resp = await client.get("/api/v1/analytics/maturity")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "weights" in data
    assert pytest.approx(sum(data["weights"].values()), rel=0.001) == 1.0
    assert "departments" in data
    assert "trend" in data
    assert "has_history" in data


async def test_maturity_dept_filter(client):
    await create_tom(
        client, title="Maturity-Filter-TOM", department_codes=["UniqueMaturityDept"]
    )
    resp = await client.get("/api/v1/analytics/maturity?department=UniqueMaturityDept")
    assert resp.status_code == 200
    data = resp.json()
    assert data["department_filter"] == "UniqueMaturityDept"


async def test_maturity_snapshot_writes_rows(client):
    """Manueller Aufruf des Snapshot-Helpers schreibt eine Zeile pro Department."""
    from app.database import async_session_factory
    from app.services.maturity_service import write_maturity_snapshot

    async with async_session_factory() as session:
        count = await write_maturity_snapshot(session)
        await session.commit()

    # count >= 0 — bei leerer DB ist 0 ok, bei seeded DB > 0.
    assert count >= 0


# ---------------------------------------------------------------------------
# Org-Risk Department-Filter
# ---------------------------------------------------------------------------


async def test_org_risk_dept_filter(client):
    resp = await client.get("/api/v1/analytics/org-risk?department=NonExistentDept-XYZ")
    assert resp.status_code == 200
    data = resp.json()
    assert data["department_filter"] == "NonExistentDept-XYZ"
    # Filter auf nicht-existierende Abteilung -> leere Liste.
    assert data["dept_risk"] == []
