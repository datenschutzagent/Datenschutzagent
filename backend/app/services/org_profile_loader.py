"""Load organisation profile metadata (org_name, vvt_fields) from profile.yaml or env settings."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml

from app.config import Settings

logger = logging.getLogger(__name__)

_APP_DIR = Path(__file__).resolve().parent.parent
_DATA_DIR = _APP_DIR / "data"

# DSGVO Art. 30 canonical field names (default when no custom list is configured)
DEFAULT_VVT_FIELD_NAMES: list[str] = [
    "Zwecke der Verarbeitung",
    "Rechtsgrundlage",
    "Kategorien betroffener Personen",
    "Kategorien personenbezogener Daten",
    "Empfänger / Empfängerkategorien",
    "Drittlandtransfer",
    "Speicherdauer",
    "Technische und organisatorische Maßnahmen (TOMs)",
]


def _load_profile_yaml(settings: Settings) -> dict[str, Any]:
    """Load org_profiles/{org_profile}/profile.yaml if it exists, else empty dict."""
    profile = (settings.org_profile or "default").strip() or "default"
    path = _DATA_DIR / "org_profiles" / profile / "profile.yaml"
    if not path.is_file():
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return data if isinstance(data, dict) else {}
    except Exception as exc:
        logger.warning("Failed to load org profile YAML at %s: %s", path, exc)
        return {}


def get_org_name(settings: Settings) -> str:
    """
    Resolve display name for the organisation.
    Priority: settings.org_name (env ORG_NAME) > profile.yaml -> org_name > empty string.
    """
    if settings.org_name and settings.org_name.strip():
        return settings.org_name.strip()
    profile_data = _load_profile_yaml(settings)
    name = profile_data.get("org_name")
    if isinstance(name, str) and name.strip():
        return name.strip()
    return ""


def get_vvt_field_names(settings: Settings) -> list[str]:
    """
    Resolve canonical VVT field names.
    Priority:
      1. settings.vvt_field_names (env VVT_FIELD_NAMES, semicolon-separated)
      2. profile.yaml -> vvt_fields (list)
      3. DEFAULT_VVT_FIELD_NAMES (DSGVO Art. 30)
    """
    # 1. Env override (semicolon-separated)
    if settings.vvt_field_names and settings.vvt_field_names.strip():
        names = [n.strip() for n in settings.vvt_field_names.split(";") if n.strip()]
        if names:
            return names

    # 2. profile.yaml
    profile_data = _load_profile_yaml(settings)
    fields = profile_data.get("vvt_fields")
    if isinstance(fields, list):
        names = [str(f).strip() for f in fields if f and str(f).strip()]
        if names:
            return names

    # 3. Default
    return list(DEFAULT_VVT_FIELD_NAMES)


def get_processing_context_options(settings: Settings) -> list[dict[str, str]]:
    """
    Resolve processing context options for the new-case dialog.
    Priority:
      1. settings.processing_context_options (env, format: "value:Label,value2:Label2")
      2. Built-in defaults
    """
    if (
        settings.processing_context_options
        and settings.processing_context_options.strip()
    ):
        options: list[dict[str, str]] = []
        for entry in settings.processing_context_options.split(","):
            entry = entry.strip()
            if not entry:
                continue
            if ":" in entry:
                value, _, label = entry.partition(":")
                options.append({"value": value.strip(), "label": label.strip()})
            else:
                options.append({"value": entry, "label": entry})
        if options:
            return options

    return [
        {"value": "none", "label": "Keiner / nicht festgelegt"},
        {"value": "research", "label": "Forschung"},
        {"value": "hr", "label": "Personal"},
        {"value": "it_operations", "label": "IT-Betrieb"},
        {"value": "communications", "label": "Öffentlichkeitsarbeit / Kommunikation"},
        {"value": "procurement", "label": "Beschaffung"},
        {"value": "other", "label": "Sonstiges"},
    ]
