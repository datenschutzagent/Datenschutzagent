"""Load risk-model configuration (thresholds, weights) from YAML per org profile.

Risk thresholds and weights that were previously hardcoded across the risk-model
services (AVV, DSFA, Case-Score, Maturity) are externalised here. Resolution
follows the same pattern as ``org_profile_loader.py``:

    env override → org_profiles/{profile}/risk_config.yaml → built-in defaults

Missing files, missing sections, or missing individual fields all fall back to
the built-in defaults — so removing the YAML entirely keeps the original
behaviour bit-for-bit.
"""

from __future__ import annotations

import logging
from datetime import UTC
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from app.config import Settings
from app.config import settings as default_settings
from app.services.risk_config_models import *  # noqa: F401, F403
from app.services.risk_config_models import RiskConfig

logger = logging.getLogger(__name__)

_APP_DIR = Path(__file__).resolve().parent.parent
_DATA_DIR = _APP_DIR / "data"


# ---------------------------------------------------------------------------
# Resolution + loading
# ---------------------------------------------------------------------------


def resolve_risk_config_path(settings: Settings) -> Path | None:
    """Resolve the YAML path for the current org profile, or None if no file exists.

    Resolution order:
    1. ``settings.risk_config_path`` (env override; absolute or relative to data dir)
    2. ``data/org_profiles/{org_profile}/risk_config.yaml`` if present
    3. ``None`` — caller falls back to built-in defaults
    """
    override = (getattr(settings, "risk_config_path", None) or "").strip()
    if override:
        path = Path(override)
        if not path.is_absolute():
            path = _DATA_DIR / path
        return path
    profile = (settings.org_profile or "default").strip() or "default"
    candidate = _DATA_DIR / "org_profiles" / profile / "risk_config.yaml"
    if candidate.is_file():
        return candidate
    return None


def _load_yaml(path: Path) -> dict[str, Any]:
    try:
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except (OSError, yaml.YAMLError) as exc:
        logger.warning("Failed to read risk_config YAML at %s: %s", path, exc)
        return {}
    return data if isinstance(data, dict) else {}


def load_risk_config(settings: Settings) -> RiskConfig:
    """Load and validate the risk config for the current settings.

    Returns built-in defaults on missing file, missing sections, or validation
    errors — never raises, so a malformed YAML can't crash the API.
    """
    path = resolve_risk_config_path(settings)
    if path is None or not path.is_file():
        return RiskConfig()
    raw = _load_yaml(path)
    if not raw:
        return RiskConfig()
    try:
        return RiskConfig.model_validate(raw)
    except Exception as exc:
        logger.warning(
            "risk_config at %s failed validation, using defaults: %s",
            path,
            exc,
        )
        return RiskConfig()


@lru_cache(maxsize=8)
def _cached_config_for_key(cache_key: str) -> RiskConfig:
    """Internal: cache by profile name + override path (the only inputs to resolution)."""
    return load_risk_config(default_settings)


def get_risk_config(settings: Settings | None = None) -> RiskConfig:
    """Return the cached risk config for the active settings.

    ``settings`` defaults to the application singleton. The cache key combines
    the org profile and the override path, so changes to env vars between
    requests are picked up on next call after ``reload_risk_config()``.
    """
    s = settings or default_settings
    key = f"{s.org_profile or 'default'}|{(getattr(s, 'risk_config_path', '') or '').strip()}"
    # The cache value is computed via load_risk_config(default_settings) — but
    # for non-default callers (tests passing custom settings) we bypass the cache.
    if settings is None or settings is default_settings:
        return _cached_config_for_key(key)
    return load_risk_config(s)


def reload_risk_config() -> None:
    """Invalidate the cache — call after editing risk_config.yaml at runtime."""
    _cached_config_for_key.cache_clear()


def resolve_writable_risk_config_path(settings: Settings) -> Path:
    """Return the YAML path used for *writing* — even if no file exists yet.

    Used by the admin-API to persist changes; mirrors the read-side
    resolution but always returns a concrete path (no None).
    """
    override = (getattr(settings, "risk_config_path", None) or "").strip()
    if override:
        path = Path(override)
        if not path.is_absolute():
            path = _DATA_DIR / path
        return path
    profile = (settings.org_profile or "default").strip() or "default"
    return _DATA_DIR / "org_profiles" / profile / "risk_config.yaml"


def save_risk_config(cfg: RiskConfig, settings: Settings | None = None) -> Path:
    """Persist a validated RiskConfig to YAML and refresh the cache.

    Writes a ``.bak.{timestamp}`` snapshot of the previous file before
    overwriting, so an admin can recover from a bad change. Raises on
    I/O errors so the caller can return 500 / 422 appropriately.

    Returns the path that was written to.
    """
    from datetime import datetime

    s = settings or default_settings
    path = resolve_writable_risk_config_path(s)
    path.parent.mkdir(parents=True, exist_ok=True)

    if path.is_file():
        ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        backup = path.with_suffix(path.suffix + f".bak.{ts}")
        try:
            backup.write_bytes(path.read_bytes())
        except OSError as exc:
            logger.warning("Failed to write risk_config backup at %s: %s", backup, exc)

    payload = cfg.model_dump(mode="json")
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(
            payload, f, allow_unicode=True, sort_keys=False, default_flow_style=False
        )

    reload_risk_config()
    return path
