"""Pure tests for the concurrency / advisory-lock helpers.

We can't easily spin up Postgres in a pure test, but the key derivation
must be:
  - Deterministic across processes (BLAKE2b, not Python's random hash()).
  - Non-negative and fit in 63 bits (Postgres bigint advisory keys).
  - Domain-tagged (run_checks and dsfa should map to different keys for
    the same UUID input).
"""
from __future__ import annotations

from uuid import UUID

from app.core.concurrency import _stable_key


_CASE_A = UUID("11111111-1111-1111-1111-111111111111")
_CASE_B = UUID("22222222-2222-2222-2222-222222222222")
_PLAYBOOK = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")


def test_stable_key_is_deterministic():
    a = _stable_key("run_checks", str(_CASE_A), str(_PLAYBOOK))
    b = _stable_key("run_checks", str(_CASE_A), str(_PLAYBOOK))
    assert a == b


def test_stable_key_fits_63_bits():
    """Postgres bigint advisory keys are signed 64-bit; we ensure non-negative."""
    k = _stable_key("run_checks", str(_CASE_A), str(_PLAYBOOK))
    assert 0 <= k < (1 << 63)


def test_stable_key_distinguishes_cases():
    a = _stable_key("run_checks", str(_CASE_A), str(_PLAYBOOK))
    b = _stable_key("run_checks", str(_CASE_B), str(_PLAYBOOK))
    assert a != b


def test_stable_key_domain_tag_changes_key():
    """run_checks and dsfa keys for the same case must not collide."""
    runs = _stable_key("run_checks", str(_CASE_A))
    dsfa = _stable_key("dsfa_generate", str(_CASE_A))
    assert runs != dsfa


def test_stable_key_requires_at_least_one_part():
    import pytest
    with pytest.raises(ValueError):
        _stable_key()


# ---------------------------------------------------------------------------
# Global LLM semaphore: nested parallelism never exceeds max_concurrent_llm_calls
# ---------------------------------------------------------------------------


def test_llm_calls_respect_global_concurrency_cap(monkeypatch):
    import asyncio
    from types import SimpleNamespace

    from app.config import settings
    from app.core import llm

    monkeypatch.setattr(settings, "max_concurrent_llm_calls", 2, raising=False)

    tracker = {"cur": 0, "max": 0}

    class _StubAgent:
        async def run(self, user_content, output_type=None):
            tracker["cur"] += 1
            tracker["max"] = max(tracker["max"], tracker["cur"])
            await asyncio.sleep(0.01)
            tracker["cur"] -= 1
            return SimpleNamespace(output="ok", usage=lambda: None)

    async def main():
        agent = _StubAgent()
        await asyncio.gather(
            *(llm.llm_retry_call(agent, "u", output_type=str) for _ in range(6))
        )

    asyncio.run(main())
    assert tracker["max"] <= 2  # cap enforced even with 6-way fan-out
    assert tracker["max"] == 2  # and parallelism actually happens up to the cap
