"""Pytest configuration and fixtures for backend tests."""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

# Disable Ollama health check in tests so /health does not require Ollama
os.environ.setdefault("OLLAMA_ENABLED", "false")
# Use admin role so the default test user can perform write operations (create/update/delete)
os.environ.setdefault("RBAC_DEFAULT_ROLE", "admin")
# Disable Celery so document extraction runs inline (Redis not available in test env)
os.environ.setdefault("CELERY_ENABLED", "false")
# Mark environment as test so the production-profile validator stays lenient.
os.environ.setdefault("APP_ENVIRONMENT", "test")

# Disable rate limiting in tests: the whole suite shares the single default user,
# so per-user buckets (e.g. 30/min on case creation) would trip across unrelated
# tests that each legitimately create a handful of cases. The key function itself
# stays covered by test_rate_limit_keyfunc.py.
from app.core.rate_limit import limiter  # noqa: E402

limiter.enabled = False


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture(scope="session", autouse=True)
def _seed_database():
    """Create tables and the default user once per test session.

    The httpx ASGITransport client does not run the app lifespan, so the table creation
    (init_db) and default-user seeding that production startup performs never happen in
    tests — every DB-bound API test would 404 on the current-user lookup. Runs in its own
    event loop; the engine is disposed afterwards because asyncpg connections are bound to
    the loop they were created on.
    """
    if not (os.environ.get("DATABASE_URL") or "").strip():
        yield  # pure tests without a database
        return
    import asyncio

    async def _seed() -> None:
        from sqlalchemy import select

        from app.config import settings
        from app.database import async_session_factory, engine, init_db
        from app.main import DEFAULT_USER_ID
        from app.models.db import UserModel

        await init_db()
        async with async_session_factory() as session:
            res = await session.execute(
                select(UserModel).where(UserModel.id == DEFAULT_USER_ID)
            )
            if res.scalar_one_or_none() is None:
                session.add(
                    UserModel(
                        id=DEFAULT_USER_ID,
                        display_name=settings.default_user_display_name,
                        email=None,
                        role=settings.rbac_default_role,
                        preferences={"theme": "system", "language": "de"},
                    )
                )
                await session.commit()
        await engine.dispose()  # connections are bound to this throwaway loop

    asyncio.run(_seed())
    yield


@pytest.fixture
async def client():
    """Async HTTP client for the FastAPI app. Requires DATABASE_URL (e.g. postgres)."""
    from app.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


class _FakeLLMResult:
    """Minimal stand-in for a pydantic_ai RunResult.

    Tests that need a specific output type should set `result.output` on the
    instance returned by `agent_run_mock.return_value` before exercising the
    code under test.
    """

    def __init__(self, output=None):
        self.output = output
        # Legacy alias (some older services access .data)
        self.data = output


@pytest.fixture
def mock_llm(monkeypatch):
    """Patch the LLM layer so tests never hit a real provider.

    Yields a MagicMock that represents the fake pydantic_ai Agent. Its `.run`
    attribute is an AsyncMock, so tests can control the returned value::

        async def test_something(mock_llm):
            from app.models.schemas import FindingSeverityEnum
            from app.services.check_runner import CheckResult
            mock_llm.run.return_value = _FakeLLMResult(
                CheckResult(
                    is_compliant=True,
                    severity=FindingSeverityEnum.low,
                    description="ok",
                    evidence=[],
                    recommendation="",
                )
            )
            # … exercise the service under test …

    By default `.run` returns a ``_FakeLLMResult(output=None)`` which is safe
    for smoke tests that only care about reaching the LLM call without error.
    """
    fake_agent = MagicMock()
    fake_agent.run = AsyncMock(return_value=_FakeLLMResult())

    with patch("app.core.llm.create_agent", return_value=fake_agent) as _create, patch(
        "app.core.llm.llm_retry_call", new_callable=AsyncMock
    ) as retry_mock:
        retry_mock.return_value = _FakeLLMResult()
        fake_agent._retry_mock = retry_mock
        yield fake_agent
