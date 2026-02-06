"""Departments (Fachbereiche and central institutions) from config YAML."""
from pathlib import Path

import yaml
from fastapi import APIRouter

router = APIRouter()

# Resolve path to data/fachbereiche.yaml relative to this package
_DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
_FACHBEREICHE_PATH = _DATA_DIR / "fachbereiche.yaml"


def _load_departments() -> list[dict]:
    """Load departments from fachbereiche.yaml. Returns list of {code, label, type}."""
    if not _FACHBEREICHE_PATH.exists():
        return []
    with open(_FACHBEREICHE_PATH, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    items = []
    for entry in data.get("fachbereiche") or []:
        items.append({
            "code": entry.get("code", ""),
            "label": entry.get("label", ""),
            "type": entry.get("type", "fachbereich"),
        })
    for entry in data.get("zentrale_einrichtungen") or []:
        items.append({
            "code": entry.get("code", ""),
            "label": entry.get("label", ""),
            "type": entry.get("type", "zentral"),
        })
    return items


@router.get("", response_model=list[dict])
async def list_departments():
    """
    List all departments (Fachbereiche and central institutions).
    Used for case creation and playbook assignment. No DB access.
    """
    items = _load_departments()
    # Return value suitable for dropdown: display string = "code – label"
    return [
        {
            "code": item["code"],
            "label": item["label"],
            "type": item["type"],
            "value": f"{item['code']} – {item['label']}" if item["code"] and item["label"] else (item["label"] or item["code"]),
        }
        for item in items
    ]
