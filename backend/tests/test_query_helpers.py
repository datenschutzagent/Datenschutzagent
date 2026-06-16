"""Tests for app.services.query_helpers (central eager-loading helpers).

Two layers:
- Pure unit tests for the loader-option builders (no database).
- N+1 regression tests proving the query count is constant regardless of the
  number of related rows (requires DATABASE_URL).
"""

import os
import uuid

import pytest

from app.services.query_helpers import (
    case_relations,
    finding_relations,
    select_case_by_id,
)

# asyncio_mode=auto (pytest.ini) runs async tests without an explicit marker,
# so no module-level pytestmark — it would warn on the sync unit tests below.

_HAS_DB = bool((os.environ.get("DATABASE_URL") or "").strip())
_requires_db = pytest.mark.skipif(not _HAS_DB, reason="requires a database")


# ---------------------------------------------------------------------------
# Pure unit tests — option builders (no DB)
# ---------------------------------------------------------------------------


def test_case_relations_flag_combinations():
    assert len(case_relations()) == 2  # documents + findings (default)
    assert len(case_relations(findings=False)) == 1  # documents only
    assert len(case_relations(documents=False)) == 1  # findings only
    assert len(case_relations(privacy_policies=True)) == 3  # + privacy_policies
    assert case_relations(documents=False, findings=False) == []


def test_finding_relations_flag_combinations():
    assert len(finding_relations()) == 1  # case
    assert finding_relations(case=False) == []


def test_select_case_by_id_builds_select():
    from sqlalchemy import Select

    stmt = select_case_by_id(uuid.uuid4())
    assert isinstance(stmt, Select)
    # documents + findings eager-load options are attached.
    assert len(stmt._with_options) == 2


# ---------------------------------------------------------------------------
# N+1 regression tests (require a database)
# ---------------------------------------------------------------------------


async def _create_case_with_children(n_docs: int, n_findings: int) -> uuid.UUID:
    from app.database import async_session_factory
    from app.models.db import CaseModel, DocumentModel, FindingModel

    case_id = uuid.uuid4()
    async with async_session_factory() as session:
        session.add(
            CaseModel(
                id=case_id,
                title="Query-Helper Test",
                department="IT",
                case_type="Test",
            )
        )
        for i in range(n_docs):
            session.add(
                DocumentModel(
                    case_id=case_id,
                    name=f"doc-{i}",
                    type="other",
                    format="pdf",
                    size_bytes=10,
                    storage_path=f"test/{case_id}/{i}",
                )
            )
        for i in range(n_findings):
            session.add(
                FindingModel(
                    case_id=case_id,
                    check_name=f"check-{i}",
                    severity="low",
                    category="test",
                    description="desc",
                )
            )
        await session.commit()
    return case_id


async def _load_and_count(case_id: uuid.UUID) -> int:
    from app.database import async_session_factory, engine
    from tests.utils.query_counter import QueryCounter

    async with async_session_factory() as session:
        with QueryCounter(engine) as counter:
            result = await session.execute(select_case_by_id(case_id))
            case = result.scalar_one()
            # Accessing the relations must NOT emit extra queries — they were
            # eager-loaded. If they weren't, this would lazy-load (or raise
            # MissingGreenlet in async) and bump the counter.
            assert len(case.documents) >= 0
            assert len(case.findings) >= 0
        return counter.select_count


@_requires_db
async def test_select_case_by_id_has_no_n_plus_one():
    """Query count stays constant no matter how many docs/findings exist."""
    small = await _create_case_with_children(n_docs=1, n_findings=1)
    large = await _create_case_with_children(n_docs=6, n_findings=8)

    count_small = await _load_and_count(small)
    count_large = await _load_and_count(large)

    # Constant query count regardless of child-row count == no N+1.
    assert count_small == count_large
    # base SELECT + one selectinload per eager relation (documents, findings).
    assert count_small == 3


@_requires_db
async def test_case_relations_findings_only_skips_documents_query():
    """Disabling a relation drops exactly its eager-load query."""
    from sqlalchemy import select

    from app.database import async_session_factory, engine
    from app.models.db import CaseModel
    from tests.utils.query_counter import QueryCounter

    case_id = await _create_case_with_children(n_docs=3, n_findings=3)
    async with async_session_factory() as session:
        with QueryCounter(engine) as counter:
            result = await session.execute(
                select(CaseModel)
                .where(CaseModel.id == case_id)
                .options(*case_relations(documents=False))
            )
            case = result.scalar_one()
            assert len(case.findings) == 3
        # base SELECT + one selectinload (findings) == 2, no documents query.
        assert counter.select_count == 2
