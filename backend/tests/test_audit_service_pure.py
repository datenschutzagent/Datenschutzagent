"""Pure tests for the audit hash function (no DB)."""

import uuid
from datetime import UTC, datetime

from app.services.audit_service import GENESIS_HASH, compute_entry_hash


def _fields(**overrides):
    base = {
        "prev_hash": None,
        "entry_id": uuid.UUID("11111111-1111-4111-8111-111111111111"),
        "user_id": uuid.UUID("22222222-2222-4222-8222-222222222222"),
        "endpoint": "/api/v1/cases",
        "method": "POST",
        "status_code": 201,
        "request_id": "req-1",
        "resource_id": None,
        "timestamp": datetime(2026, 9, 5, 12, 0, tzinfo=UTC),
    }
    base.update(overrides)
    return base


def test_hash_is_deterministic_and_64_hex():
    a = compute_entry_hash(**_fields())
    b = compute_entry_hash(**_fields())
    assert a == b
    assert len(a) == 64 and int(a, 16) >= 0


def test_hash_changes_with_every_field():
    base = compute_entry_hash(**_fields())
    variants = [
        _fields(prev_hash="ab" * 32),
        _fields(status_code=200),
        _fields(endpoint="/api/v1/cases/{id}"),
        _fields(method="PATCH"),
        _fields(user_id=None),
        _fields(request_id="req-2"),
        _fields(resource_id="doc-1"),
        _fields(timestamp=datetime(2026, 9, 5, 12, 0, 1, tzinfo=UTC)),
    ]
    assert (
        len({compute_entry_hash(**v) for v in variants} | {base}) == len(variants) + 1
    )


def test_missing_prev_hash_uses_genesis():
    assert compute_entry_hash(**_fields(prev_hash=None)) == compute_entry_hash(
        **_fields(prev_hash=GENESIS_HASH)
    )
