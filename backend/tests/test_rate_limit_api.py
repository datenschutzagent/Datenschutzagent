"""The rate limiter is disabled for the suite (conftest) – this is the one test that
switches it on and proves a bucket actually returns 429 through the real middleware.
"""

import uuid

import pytest

from app.core.rate_limit import limiter


@pytest.fixture
def _limiter_enabled():
    limiter.enabled = True
    limiter.reset()
    try:
        yield
    finally:
        limiter.enabled = False
        limiter.reset()


async def test_sixth_call_within_a_minute_is_rate_limited(client, _limiter_enabled):
    """POST /avv/{id}/risk-assessment is limited to 5/minute; the request is counted
    before the handler runs, so a non-existent id keeps the test cheap (404, no LLM)."""
    path = f"/api/v1/avv/{uuid.uuid4()}/risk-assessment"
    statuses = [(await client.post(path)).status_code for _ in range(6)]
    assert statuses[:5] == [404] * 5, statuses
    assert statuses[5] == 429, statuses
    # Stays limited until the window rolls over.
    assert (await client.post(path)).status_code == 429
