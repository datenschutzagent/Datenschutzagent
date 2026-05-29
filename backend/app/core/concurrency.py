"""Postgres advisory-lock helpers — Phase 4 concurrency hardening.

Used to serialise expensive, side-effect-heavy operations (playbook check
runs, DSFA generation) for the same case so two concurrent requests
cannot create duplicate jobs or duplicate findings.

We use **transaction-scoped** advisory locks (``pg_try_advisory_xact_lock``)
so the lock is released automatically at commit/rollback — no risk of a
permanently stuck row when a worker dies. ``pg_try_*`` returns false
instead of blocking, which lets the API surface HTTP 423 immediately
instead of holding the connection.

The lock key is a 64-bit int derived from a stable string hash so the same
``(case_id, playbook_id)`` pair always maps to the same slot across
processes. We use BLAKE2b (stdlib, cryptographic) truncated to 8 bytes for
distribution; Python's built-in ``hash()`` cannot be used because it
randomises across processes.
"""
from __future__ import annotations

import hashlib
import logging
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


# Postgres advisory lock keys are 64-bit signed integers (bigint). We
# compute a stable 63-bit unsigned int from a domain-tagged string and
# cast to signed at the SQL boundary.
_KEY_MASK = (1 << 63) - 1  # 63-bit mask keeps the value non-negative


def _stable_key(*parts: str) -> int:
    """Stable, process-independent 63-bit lock key from string parts.

    Domain-tag your keys (e.g. ``("run_checks", str(case_id))``) so two
    unrelated subsystems can't collide.
    """
    if not parts:
        raise ValueError("at least one key part required")
    digest = hashlib.blake2b("\x00".join(parts).encode("utf-8"), digest_size=8).digest()
    return int.from_bytes(digest, "big", signed=False) & _KEY_MASK


async def try_acquire_run_checks_lock(
    db: AsyncSession, case_id: UUID, playbook_id: UUID
) -> bool:
    """Try to acquire the playbook-run lock for ``(case_id, playbook_id)``.

    Returns True if the lock was acquired (caller now owns it until the
    current transaction ends), False if another transaction holds it.
    Never blocks — uses ``pg_try_advisory_xact_lock``.
    """
    key = _stable_key("run_checks", str(case_id), str(playbook_id))
    result = await db.execute(
        text("SELECT pg_try_advisory_xact_lock(:k)"), {"k": key}
    )
    acquired = bool(result.scalar())
    if not acquired:
        logger.info(
            "run_checks advisory lock not acquired — concurrent run detected",
            extra={"case_id": str(case_id), "playbook_id": str(playbook_id), "lock_key": key},
        )
    return acquired


async def try_acquire_dsfa_lock(db: AsyncSession, case_id: UUID) -> bool:
    """Try to acquire the DSFA-generation lock for a case."""
    key = _stable_key("dsfa_generate", str(case_id))
    result = await db.execute(
        text("SELECT pg_try_advisory_xact_lock(:k)"), {"k": key}
    )
    acquired = bool(result.scalar())
    if not acquired:
        logger.info(
            "dsfa advisory lock not acquired — concurrent generation detected",
            extra={"case_id": str(case_id), "lock_key": key},
        )
    return acquired


__all__ = [
    "try_acquire_run_checks_lock",
    "try_acquire_dsfa_lock",
    "_stable_key",  # exported for tests
]
