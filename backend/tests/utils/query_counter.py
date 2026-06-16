"""Count SQL statements emitted during a block — for N+1 regression tests.

Attaches a ``before_cursor_execute`` listener to the async engine's underlying
sync engine, so it captures statements from both sync and async execution::

    from app.database import engine
    from tests.utils.query_counter import QueryCounter

    with QueryCounter(engine) as counter:
        await session.execute(select_case_by_id(case_id))
    assert counter.select_count == 3  # base + selectinload(documents/findings)
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncEngine


class QueryCounter:
    """Context manager that records every SQL statement on an engine."""

    def __init__(self, engine: AsyncEngine) -> None:
        # AsyncEngine wraps a sync Engine; events fire on the sync layer.
        self._sync_engine = engine.sync_engine
        self.statements: list[str] = []

    def _on_execute(
        self,
        conn: Any,
        cursor: Any,
        statement: str,
        parameters: Any,
        context: Any,
        executemany: bool,
    ) -> None:
        self.statements.append(statement)

    @property
    def count(self) -> int:
        """Total number of executed statements."""
        return len(self.statements)

    @property
    def select_count(self) -> int:
        """Number of executed SELECT statements (the N+1-relevant ones)."""
        return sum(
            1 for s in self.statements if s.lstrip().upper().startswith("SELECT")
        )

    def __enter__(self) -> QueryCounter:
        event.listen(self._sync_engine, "before_cursor_execute", self._on_execute)
        return self

    def __exit__(self, *exc: object) -> None:
        event.remove(self._sync_engine, "before_cursor_execute", self._on_execute)
