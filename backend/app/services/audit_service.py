"""API audit log: hash-chained, append-only records (Qualitätsplan Phase 1 S6).

Every audited request appends one row whose ``entry_hash`` covers the previous row's
hash plus its own fields. Inserts are serialised with a transaction-scoped advisory
lock so concurrent requests cannot both read the same "last hash" (write volume is
low: one row per mutating request or privacy-relevant read).
"""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models._db.audit import APIAuditLogModel

# Constant key for pg_advisory_xact_lock — any int64 the app does not use elsewhere.
_AUDIT_CHAIN_LOCK_KEY = 0x5A_5D_41_55_44_49_54  # "ZAUDIT"
GENESIS_HASH = "0" * 64


def compute_entry_hash(
    *,
    prev_hash: str | None,
    entry_id: uuid.UUID,
    user_id: uuid.UUID | None,
    endpoint: str,
    method: str,
    status_code: int,
    request_id: str,
    resource_id: str | None,
    timestamp: datetime,
) -> str:
    """Deterministic sha256 over the chain-relevant fields (``|``-separated)."""
    material = "|".join(
        [
            prev_hash or GENESIS_HASH,
            str(entry_id),
            str(user_id) if user_id else "",
            endpoint,
            method,
            str(status_code),
            request_id or "",
            resource_id or "",
            timestamp.astimezone(UTC).isoformat(timespec="microseconds"),
        ]
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def _hash_of(row: APIAuditLogModel, prev_hash: str | None) -> str:
    return compute_entry_hash(
        prev_hash=prev_hash,
        entry_id=row.id,
        user_id=row.user_id,
        endpoint=row.endpoint,
        method=row.method,
        status_code=row.status_code,
        request_id=row.request_id,
        resource_id=row.resource_id,
        timestamp=row.timestamp,
    )


async def record_audit_entry(
    session: AsyncSession,
    *,
    user_id: uuid.UUID | None,
    endpoint: str,
    method: str,
    status_code: int,
    request_id: str,
    resource_id: str | None = None,
) -> APIAuditLogModel:
    """Append one chained row inside ``session`` (caller commits)."""
    await session.execute(
        text("SELECT pg_advisory_xact_lock(:k)"), {"k": _AUDIT_CHAIN_LOCK_KEY}
    )
    last = (
        await session.execute(
            select(APIAuditLogModel.entry_hash)
            .order_by(APIAuditLogModel.seq.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    row = APIAuditLogModel(
        id=uuid.uuid4(),
        user_id=user_id,
        endpoint=endpoint,
        method=method,
        status_code=status_code,
        request_id=request_id or "-",
        resource_id=resource_id,
        prev_hash=last,
        timestamp=datetime.now(UTC),
    )
    row.entry_hash = _hash_of(row, last)
    session.add(row)
    await session.flush()
    return row


@dataclass
class ChainVerification:
    ok: bool
    checked: int
    skipped_unhashed: int
    first_broken_seq: int | None = None
    reason: str | None = None


async def verify_audit_chain(session: AsyncSession) -> ChainVerification:
    """Recompute every hash in ``seq`` order and compare it with the stored value.

    Rows without ``entry_hash`` (written before the chain existed) are skipped; the
    chain starts at the first hashed row. Returns the first broken position, if any.
    """
    result = await session.execute(
        select(APIAuditLogModel).order_by(APIAuditLogModel.seq.asc())
    )
    checked = skipped = 0
    prev: str | None = None
    started = False
    for row in result.scalars():
        if row.entry_hash is None:
            if started:
                return ChainVerification(
                    False, checked, skipped, row.seq, "unhashed row after chain start"
                )
            skipped += 1
            continue
        started = True
        if row.prev_hash != prev:
            return ChainVerification(
                False, checked, skipped, row.seq, "prev_hash does not match predecessor"
            )
        if _hash_of(row, prev) != row.entry_hash:
            return ChainVerification(
                False, checked, skipped, row.seq, "entry_hash mismatch (row modified?)"
            )
        prev = row.entry_hash
        checked += 1
    return ChainVerification(True, checked, skipped)
