"""Pure unit tests for retention_service (no DB needed)."""

from app.services.retention_service import _retention_base_sql


def test_retention_base_sql_require_completed(monkeypatch):
    from app.services import retention_service as rs

    monkeypatch.setattr(rs.settings, "retention_require_completed", True)
    assert _retention_base_sql() == "completed_at"


def test_retention_base_sql_fallback(monkeypatch):
    from app.services import retention_service as rs

    monkeypatch.setattr(rs.settings, "retention_require_completed", False)
    assert _retention_base_sql() == "COALESCE(completed_at, created_at)"
