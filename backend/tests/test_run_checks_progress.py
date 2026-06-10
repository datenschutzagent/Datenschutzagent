"""Tests for run-check progress / timeout decoupling in run_checks_service."""

import asyncio
import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.services.run_checks_service import _CheckRunState, _run_with_limits


def _minimal_state(
    *, on_check_done=None, timeout: float | None = 1.0
) -> _CheckRunState:
    return _CheckRunState(
        db=MagicMock(),
        case=SimpleNamespace(documents=[]),
        case_id=uuid.uuid4(),
        case_language="de",
        playbook_revision="",
        playbook_legal_ids=[],
        legal_bases_by_id={},
        existing_open=set(),
        on_check_done=on_check_done,
        semaphore=None,
        timeout=timeout,
    )


@pytest.mark.anyio
async def test_run_with_limits_progress_outside_timeout():
    """Slow progress callback must not trigger the per-check asyncio timeout."""
    progress_calls = 0

    async def _on_check_done() -> None:
        nonlocal progress_calls
        await asyncio.sleep(0.05)
        progress_calls += 1

    state = _minimal_state(on_check_done=_on_check_done, timeout=0.2)

    async def _fast_check() -> bool:
        await asyncio.sleep(0.01)
        return True

    await _run_with_limits(
        state,
        _fast_check(),
        "TestCheck",
        "document",
        uuid.uuid4(),
        "full_text",
    )

    assert state.errors == []
    assert progress_calls == 1


@pytest.mark.anyio
async def test_run_with_limits_timeout_does_not_call_progress():
    """Hung checks must time out without incrementing progress."""
    progress_calls = 0

    async def _on_check_done() -> None:
        nonlocal progress_calls
        progress_calls += 1

    state = _minimal_state(on_check_done=_on_check_done, timeout=0.05)

    async def _slow_check() -> bool:
        await asyncio.sleep(1.0)
        return True

    await _run_with_limits(
        state,
        _slow_check(),
        "SlowCheck",
        "document",
        uuid.uuid4(),
        "full_text",
    )

    assert len(state.errors) == 1
    assert "timed out" in state.errors[0]["error"]
    assert progress_calls == 0


@pytest.mark.anyio
async def test_run_with_limits_llm_error_skips_progress():
    """Failed checks (return False) must not increment progress."""
    progress_calls = 0

    async def _on_check_done() -> None:
        nonlocal progress_calls
        progress_calls += 1

    state = _minimal_state(on_check_done=_on_check_done, timeout=1.0)

    async def _failed_check() -> bool:
        return False

    await _run_with_limits(
        state,
        _failed_check(),
        "FailedCheck",
        "document",
        uuid.uuid4(),
        "full_text",
    )

    assert state.errors == []
    assert progress_calls == 0
