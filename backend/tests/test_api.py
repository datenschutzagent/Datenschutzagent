"""API route tests. Require DATABASE_URL (e.g. postgres) for app lifespan."""
import os

import pytest

pytestmark = pytest.mark.asyncio


async def test_health(client):
    """GET /health returns 200 and status."""
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert data["status"] in ("ok", "degraded")


async def test_departments_list(client):
    """GET /api/v1/departments returns 200 and a list."""
    response = await client.get("/api/v1/departments")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


async def test_cases_list(client):
    """GET /api/v1/cases returns 200 and a list."""
    response = await client.get("/api/v1/cases")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
