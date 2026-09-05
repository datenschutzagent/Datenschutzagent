"""Domain-error → Problem Details mapping (Phase 2 R3). Requires DATABASE_URL."""

from unittest.mock import AsyncMock, patch

import pytest

from app.core.exceptions import (
    LLMBudgetExceededError,
    LLMProviderError,
    LLMRetryExhaustedError,
    PromptInjectionError,
)

pytestmark = pytest.mark.asyncio


async def _case_with_finding(client) -> str:
    import uuid

    from app.database import async_session_factory
    from app.models.db import FindingModel

    resp = await client.post(
        "/api/v1/cases",
        json={
            "title": "Handler-Test",
            "department": "IT",
            "case_type": "Softwareeinführung",
            "language": "de",
        },
    )
    assert resp.status_code == 201, resp.text
    async with async_session_factory() as session:
        f = FindingModel(
            case_id=uuid.UUID(resp.json()["id"]),
            check_name="c",
            severity="high",
            category="x",
            description="d",
        )
        session.add(f)
        await session.commit()
        return str(f.id)


@pytest.mark.parametrize(
    "exc, status, code",
    [
        (LLMProviderError("provider down"), 503, "LLM_UNAVAILABLE"),
        (LLMRetryExhaustedError("all retries failed"), 503, "LLM_RETRY_EXHAUSTED"),
        (LLMBudgetExceededError("budget"), 503, "LLM_BUDGET_EXCEEDED"),
        (PromptInjectionError("rejected"), 400, "PROMPT_REJECTED"),
    ],
)
async def test_domain_errors_map_to_problem_details(client, exc, status, code):
    finding_id = await _case_with_finding(client)
    with patch(
        "app.services.finding_chat_service.chat_with_finding",
        AsyncMock(side_effect=exc),
    ):
        resp = await client.post(
            f"/api/v1/findings/{finding_id}/chat", json={"content": "Frage?"}
        )
    assert resp.status_code == status, resp.text
    body = resp.json()
    assert body["code"] == code
    assert body["detail"] == str(exc)
    assert resp.headers["content-type"].startswith("application/problem+json")


async def test_unexpected_error_does_not_leak_message(client):
    finding_id = await _case_with_finding(client)
    with patch(
        "app.services.finding_chat_service.chat_with_finding",
        AsyncMock(side_effect=RuntimeError("secret internal detail")),
    ):
        resp = await client.post(
            f"/api/v1/findings/{finding_id}/chat", json={"content": "Frage?"}
        )
    assert resp.status_code == 502
    assert "secret internal detail" not in resp.text
