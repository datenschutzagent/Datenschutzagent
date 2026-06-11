"""Resolve and load organisation units (departments) from YAML — configurable per org profile or path."""

from pathlib import Path
from typing import Any

import yaml

from app.config import Settings

# backend/app/services -> app root is parent.parent
_APP_DIR = Path(__file__).resolve().parent.parent
_DATA_DIR = _APP_DIR / "data"


def resolve_departments_yaml_path(settings: Settings) -> Path:
    """
    Resolution order:
    1. departments_config_path (env), if set — absolute or relative to app data dir
    2. data/org_profiles/{org_profile}/departments.yaml if that file exists
    3. data/fachbereiche.yaml (legacy default)
    """
    if settings.departments_config_path:
        raw = (settings.departments_config_path or "").strip()
        if raw:
            p = Path(raw)
            if not p.is_absolute():
                p = _DATA_DIR / p
            return p
    profile = (settings.org_profile or "default").strip() or "default"
    profile_path = _DATA_DIR / "org_profiles" / profile / "departments.yaml"
    if profile_path.is_file():
        return profile_path
    return _DATA_DIR / "org_profiles" / "default" / "departments.yaml"


def load_departments_from_yaml(path: Path) -> list[dict[str, Any]]:
    """
    Load departments from YAML. Supports keys fachbereiche + zentral_einrichtungen (legacy)
    or a single top-level list `units` with entries {code, label, type}.
    """
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    items: list[dict[str, Any]] = []
    if isinstance(data.get("units"), list):
        for entry in data["units"]:
            if not isinstance(entry, dict):
                continue
            items.append(
                {
                    "code": entry.get("code", ""),
                    "label": entry.get("label", ""),
                    "type": entry.get("type", "unit"),
                }
            )
        return items
    for entry in data.get("fachbereiche") or []:
        if not isinstance(entry, dict):
            continue
        items.append(
            {
                "code": entry.get("code", ""),
                "label": entry.get("label", ""),
                "type": entry.get("type", "fachbereich"),
            }
        )
    for entry in data.get("zentrale_einrichtungen") or []:
        if not isinstance(entry, dict):
            continue
        items.append(
            {
                "code": entry.get("code", ""),
                "label": entry.get("label", ""),
                "type": entry.get("type", "zentral"),
            }
        )
    return items


def departments_for_api(settings: Settings) -> list[dict[str, str]]:
    """Load departments and shape for GET /departments (code, label, type, value)."""
    path = resolve_departments_yaml_path(settings)
    raw_items = load_departments_from_yaml(path)
    out: list[dict[str, str]] = []
    for item in raw_items:
        code = str(item.get("code") or "")
        label = str(item.get("label") or "")
        typ = str(item.get("type") or "")
        value = f"{code} – {label}" if code and label else (label or code)
        out.append({"code": code, "label": label, "type": typ, "value": value})
    return out
