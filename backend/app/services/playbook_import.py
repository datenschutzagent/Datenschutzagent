"""Import playbooks from YAML files when the playbooks table is empty."""
from pathlib import Path
from typing import Any

import yaml
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db import PlaybookModel


def _default_playbooks_dir() -> Path:
    """Default directory for playbook YAML files (app/data/playbooks)."""
    return Path(__file__).resolve().parent.parent / "data" / "playbooks"


def _load_playbook_yaml(path: Path) -> dict[str, Any] | None:
    """Load a single playbook YAML file. Returns dict or None on error."""
    if not path.suffix.lower() in (".yaml", ".yml"):
        return None
    try:
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        if not isinstance(data, dict):
            return None
        return data
    except Exception:
        return None


def _normalize_check_scope(item: dict[str, Any]) -> dict[str, Any]:
    """Ensure each check has a scope: document (default) or case/cross_document."""
    scope = item.get("scope") or item.get("type") or "document"
    if scope in ("case", "cross_document"):
        scope = "case"  # normalize for run_checks
    else:
        scope = "document"
    return {**item, "scope": scope}


def _yaml_to_model_data(data: dict[str, Any]) -> dict[str, Any] | None:
    """
    Convert YAML playbook dict to fields for PlaybookModel.
    Expects: name, version, department, optional case_type, checks (list of {name, instruction, ...}).
    Each check may have scope or type: "document" (default) or "case"/"cross_document".
    """
    name = data.get("name")
    version = data.get("version")
    if not name or not version:
        return None
    checks = data.get("checks")
    if not isinstance(checks, list):
        checks = []
    normalized = [_normalize_check_scope(c) if isinstance(c, dict) else c for c in checks]
    content: dict[str, Any] = {"checks": normalized}
    legal_basis_ids = data.get("legal_basis_ids")
    if isinstance(legal_basis_ids, list):
        content["legal_basis_ids"] = [str(x) for x in legal_basis_ids]
    return {
        "name": str(name),
        "version": str(version),
        "content": content,
        "case_type": data.get("case_type"),
        "department": data.get("department"),
        "is_active": True,
    }


async def import_playbooks_from_yaml(
    db: AsyncSession,
    seed_dir: Path | None = None,
) -> int:
    """
    Load all .yaml/.yml files from seed_dir and insert as PlaybookModel.
    Returns number of playbooks inserted. Does not run if playbooks already exist.
    """
    dir_path = seed_dir or _default_playbooks_dir()
    if not dir_path.is_dir():
        return 0

    result = await db.execute(select(PlaybookModel))
    if result.scalars().first() is not None:
        return 0

    count = 0
    for path in sorted(dir_path.iterdir()):
        if not path.is_file():
            continue
        data = _load_playbook_yaml(path)
        if not data:
            continue
        model_data = _yaml_to_model_data(data)
        if not model_data:
            continue
        db.add(PlaybookModel(**model_data))
        count += 1
    return count
