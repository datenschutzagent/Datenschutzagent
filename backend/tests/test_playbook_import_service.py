"""Unit tests for import_playbooks_from_yaml() in playbook_import.py.

Uses a real temp directory (pytest tmp_path) for YAML files and mocks
the database session to avoid a live PostgreSQL connection.
"""
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.playbook_import import import_playbooks_from_yaml

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

VALID_PLAYBOOK_YAML = """\
name: Test Playbook
version: "1.0"
department: IT
checks:
  - name: Check A
    instruction: "Check something"
    scope: document
  - name: Check B
    instruction: "Check another thing"
    scope: case
"""

MINIMAL_PLAYBOOK_YAML = """\
name: Minimal
version: "2.0"
checks: []
"""

INVALID_PLAYBOOK_YAML = """\
- this
- is
- a list
- not a dict
"""

MISSING_NAME_YAML = """\
version: "1.0"
checks: []
"""


def _make_db_no_existing_playbooks() -> AsyncMock:
    """DB session mock that reports no existing playbooks (empty table)."""
    db = AsyncMock()
    mock_scalars = MagicMock()
    mock_scalars.first.return_value = None
    db.execute.return_value.scalars.return_value = mock_scalars
    return db


def _make_db_with_existing_playbooks() -> AsyncMock:
    """DB session mock that reports at least one existing playbook."""
    db = AsyncMock()
    mock_scalars = MagicMock()
    mock_scalars.first.return_value = MagicMock()  # Non-None → skip import
    db.execute.return_value.scalars.return_value = mock_scalars
    return db


# ---------------------------------------------------------------------------
# import_playbooks_from_yaml
# ---------------------------------------------------------------------------


async def test_import_inserts_valid_playbooks(tmp_path):
    """Valid YAML files result in PlaybookModel.add() calls."""
    (tmp_path / "playbook1.yaml").write_text(VALID_PLAYBOOK_YAML, encoding="utf-8")
    (tmp_path / "playbook2.yml").write_text(MINIMAL_PLAYBOOK_YAML, encoding="utf-8")

    db = _make_db_no_existing_playbooks()
    count = await import_playbooks_from_yaml(db, seed_dir=tmp_path)

    assert count == 2
    assert db.add.call_count == 2


async def test_import_skips_when_playbooks_already_exist(tmp_path):
    """Does not import if the playbooks table is non-empty."""
    (tmp_path / "playbook.yaml").write_text(VALID_PLAYBOOK_YAML, encoding="utf-8")

    db = _make_db_with_existing_playbooks()
    count = await import_playbooks_from_yaml(db, seed_dir=tmp_path)

    assert count == 0
    db.add.assert_not_called()


async def test_import_skips_invalid_yaml(tmp_path):
    """Files with non-dict YAML root are silently skipped."""
    (tmp_path / "bad.yaml").write_text(INVALID_PLAYBOOK_YAML, encoding="utf-8")
    (tmp_path / "good.yaml").write_text(VALID_PLAYBOOK_YAML, encoding="utf-8")

    db = _make_db_no_existing_playbooks()
    count = await import_playbooks_from_yaml(db, seed_dir=tmp_path)

    assert count == 1


async def test_import_skips_missing_name(tmp_path):
    """YAML without a name field is skipped (returns None from _yaml_to_model_data)."""
    (tmp_path / "no_name.yaml").write_text(MISSING_NAME_YAML, encoding="utf-8")

    db = _make_db_no_existing_playbooks()
    count = await import_playbooks_from_yaml(db, seed_dir=tmp_path)

    assert count == 0


async def test_import_skips_non_yaml_files(tmp_path):
    """Non-.yaml/.yml files in the directory are ignored."""
    (tmp_path / "playbook.yaml").write_text(VALID_PLAYBOOK_YAML, encoding="utf-8")
    (tmp_path / "README.txt").write_text("documentation", encoding="utf-8")
    (tmp_path / "config.json").write_text('{"key": "val"}', encoding="utf-8")

    db = _make_db_no_existing_playbooks()
    count = await import_playbooks_from_yaml(db, seed_dir=tmp_path)

    assert count == 1  # Only the .yaml file was imported


async def test_import_nonexistent_directory_returns_zero():
    """If seed_dir doesn't exist, returns 0 without error."""
    db = _make_db_no_existing_playbooks()
    count = await import_playbooks_from_yaml(db, seed_dir=Path("/nonexistent/path"))
    assert count == 0
    db.add.assert_not_called()


async def test_import_empty_directory_returns_zero(tmp_path):
    """An empty seed directory results in 0 imports."""
    db = _make_db_no_existing_playbooks()
    count = await import_playbooks_from_yaml(db, seed_dir=tmp_path)
    assert count == 0


async def test_import_check_scopes_normalized(tmp_path):
    """Imported checks have their scope normalized (cross_document → case)."""
    yaml_content = """\
name: Scope Test
version: "1.0"
checks:
  - name: Case Check
    scope: cross_document
    instruction: "test"
  - name: Doc Check
    scope: document
    instruction: "test"
"""
    (tmp_path / "scoped.yaml").write_text(yaml_content, encoding="utf-8")

    db = _make_db_no_existing_playbooks()
    await import_playbooks_from_yaml(db, seed_dir=tmp_path)

    # Retrieve the PlaybookModel passed to db.add()
    call_args = db.add.call_args
    added_model = call_args[0][0]
    checks = added_model.content["checks"]
    assert checks[0]["scope"] == "case"
    assert checks[1]["scope"] == "document"
