"""Pytest configuration and fixtures for backend tests."""
import os

import pytest
from httpx import ASGITransport, AsyncClient

# Disable Ollama health check in tests so /health does not require Ollama
os.environ.setdefault("OLLAMA_ENABLED", "false")
# Use admin role so the default test user can perform write operations (create/update/delete)
os.environ.setdefault("RBAC_DEFAULT_ROLE", "admin")
# Disable Celery so document extraction runs inline (Redis not available in test env)
os.environ.setdefault("CELERY_ENABLED", "false")


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def client():
    """Async HTTP client for the FastAPI app. Requires DATABASE_URL (e.g. postgres) for lifespan."""
    from app.main import app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
