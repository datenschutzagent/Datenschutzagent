"""Pure unit tests for app.services.org_profile_loader (no DB, no LLM).

The loader resolves org metadata with the priority env settings > profile.yaml >
built-in defaults. Custom profiles are written to ``tmp_path`` and the module's
data directory is redirected via ``monkeypatch`` so the shipped profiles stay
untouched.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from app.config import Settings
from app.services import org_profile_loader as loader
from app.services.org_profile_loader import (
    DEFAULT_VVT_FIELD_NAMES,
    _load_profile_yaml,
    get_org_name,
    get_processing_context_options,
    get_vvt_field_names,
)


def _settings(**overrides) -> Settings:
    """Settings with every loader-relevant field pinned to a known value.

    Explicit kwargs take precedence over env/.env, so the tests are independent of
    ORG_NAME / VVT_FIELD_NAMES / ... in the developer's environment.
    """
    base = {
        "org_profile": "default",
        "org_name": "",
        "vvt_field_names": "",
        "processing_context_options": "",
    }
    base.update(overrides)
    return Settings(**base)


def _write_profile(data_dir: Path, profile: str, text: str) -> Path:
    path = data_dir / "org_profiles" / profile / "profile.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


@pytest.fixture
def data_dir(tmp_path: Path, monkeypatch) -> Path:
    """Redirect the loader's data directory to an isolated temp folder."""
    monkeypatch.setattr(loader, "_DATA_DIR", tmp_path)
    return tmp_path


# ---------------------------------------------------------------------------
# _load_profile_yaml
# ---------------------------------------------------------------------------


def test_load_shipped_default_profile_is_dict():
    """The profile shipped under app/data/org_profiles/default is loadable."""
    data = _load_profile_yaml(_settings(org_profile="default"))
    assert isinstance(data, dict)
    # The shipped default deliberately keeps org_name empty (set via ORG_NAME env).
    assert data.get("org_name", "") == ""


def test_load_profile_missing_file_returns_empty(data_dir: Path):
    assert _load_profile_yaml(_settings(org_profile="does-not-exist")) == {}


@pytest.mark.parametrize("profile_value", ["", "   ", None])
def test_load_profile_blank_name_falls_back_to_default(
    data_dir: Path, profile_value, monkeypatch
):
    _write_profile(data_dir, "default", "org_name: Fallback GmbH\n")
    s = _settings()
    # Bypass pydantic validation to simulate an empty/None org_profile.
    monkeypatch.setattr(s, "org_profile", profile_value, raising=False)
    assert _load_profile_yaml(s) == {"org_name": "Fallback GmbH"}


def test_load_profile_strips_whitespace_in_name(data_dir: Path):
    _write_profile(data_dir, "acme", "org_name: ACME\n")
    assert _load_profile_yaml(_settings(org_profile="  acme  ")) == {"org_name": "ACME"}


def test_load_profile_non_mapping_yaml_returns_empty(data_dir: Path):
    _write_profile(data_dir, "listy", "- eins\n- zwei\n")
    assert _load_profile_yaml(_settings(org_profile="listy")) == {}


def test_load_profile_empty_file_returns_empty(data_dir: Path):
    _write_profile(data_dir, "empty", "")
    assert _load_profile_yaml(_settings(org_profile="empty")) == {}


def test_load_profile_malformed_yaml_logs_warning_and_returns_empty(
    data_dir: Path, caplog
):
    _write_profile(data_dir, "broken", "org_name: [unclosed\n  - x: {\n")
    with caplog.at_level(logging.WARNING, logger="app.services.org_profile_loader"):
        data = _load_profile_yaml(_settings(org_profile="broken"))
    assert data == {}
    assert any("Failed to load org profile YAML" in r.message for r in caplog.records)


def test_load_profile_is_not_cached(data_dir: Path):
    """No module-level cache: a changed YAML is picked up on the next call."""
    s = _settings(org_profile="live")
    _write_profile(data_dir, "live", "org_name: Erste\n")
    assert _load_profile_yaml(s)["org_name"] == "Erste"
    _write_profile(data_dir, "live", "org_name: Zweite\n")
    assert _load_profile_yaml(s)["org_name"] == "Zweite"


# ---------------------------------------------------------------------------
# get_org_name
# ---------------------------------------------------------------------------


def test_org_name_env_wins_over_profile(data_dir: Path):
    _write_profile(data_dir, "acme", "org_name: Aus YAML\n")
    s = _settings(org_profile="acme", org_name="  Aus Env  ")
    assert get_org_name(s) == "Aus Env"


def test_org_name_from_profile_when_env_blank(data_dir: Path):
    _write_profile(data_dir, "acme", "org_name: '  Aus YAML  '\n")
    assert get_org_name(_settings(org_profile="acme", org_name="   ")) == "Aus YAML"


def test_org_name_empty_when_nothing_configured(data_dir: Path):
    assert get_org_name(_settings(org_profile="missing")) == ""


@pytest.mark.parametrize(
    "yaml_text", ["org_name: ''\n", "org_name: 42\n", "org_name:\n"]
)
def test_org_name_ignores_blank_or_non_string_profile_value(
    data_dir: Path, yaml_text: str
):
    _write_profile(data_dir, "odd", yaml_text)
    assert get_org_name(_settings(org_profile="odd")) == ""


# ---------------------------------------------------------------------------
# get_vvt_field_names
# ---------------------------------------------------------------------------


def test_vvt_fields_env_override_is_split_on_semicolon(data_dir: Path):
    _write_profile(data_dir, "acme", "vvt_fields:\n  - Aus YAML\n")
    s = _settings(org_profile="acme", vvt_field_names=" Zweck ; ; Rechtsgrundlage;")
    assert get_vvt_field_names(s) == ["Zweck", "Rechtsgrundlage"]


def test_vvt_fields_env_only_separators_falls_through_to_profile(data_dir: Path):
    _write_profile(data_dir, "acme", "vvt_fields:\n  - Aus YAML\n")
    s = _settings(org_profile="acme", vvt_field_names=" ; ; ")
    assert get_vvt_field_names(s) == ["Aus YAML"]


def test_vvt_fields_from_profile_are_stringified_and_filtered(data_dir: Path):
    _write_profile(
        data_dir,
        "acme",
        "vvt_fields:\n  - '  Zweck  '\n  - ''\n  - 7\n  - null\n  - '   '\n",
    )
    assert get_vvt_field_names(_settings(org_profile="acme")) == ["Zweck", "7"]


def test_vvt_fields_default_when_nothing_configured(data_dir: Path):
    names = get_vvt_field_names(_settings(org_profile="missing"))
    assert names == DEFAULT_VVT_FIELD_NAMES
    # Must be a copy — callers mutating the result must not alter the module default.
    assert names is not DEFAULT_VVT_FIELD_NAMES
    names.append("x")
    assert "x" not in DEFAULT_VVT_FIELD_NAMES


@pytest.mark.parametrize(
    "yaml_text",
    ["vvt_fields: []\n", "vvt_fields: 'kein array'\n", "vvt_fields:\n  - ''\n"],
)
def test_vvt_fields_invalid_profile_value_falls_back_to_default(
    data_dir: Path, yaml_text: str
):
    _write_profile(data_dir, "odd", yaml_text)
    assert get_vvt_field_names(_settings(org_profile="odd")) == DEFAULT_VVT_FIELD_NAMES


def test_shipped_default_profile_yields_art30_fields():
    """Shipped default profile has vvt_fields commented out -> DSGVO Art. 30 defaults."""
    names = get_vvt_field_names(_settings(org_profile="default"))
    assert names == DEFAULT_VVT_FIELD_NAMES
    assert len(names) == 8
    assert "Rechtsgrundlage" in names


# ---------------------------------------------------------------------------
# get_processing_context_options
# ---------------------------------------------------------------------------


def test_processing_context_defaults_when_unset():
    options = get_processing_context_options(_settings())
    values = [o["value"] for o in options]
    assert values == [
        "none",
        "research",
        "hr",
        "it_operations",
        "communications",
        "procurement",
        "other",
    ]
    assert all(set(o) == {"value", "label"} for o in options)


def test_processing_context_env_value_label_pairs():
    s = _settings(processing_context_options=" hr : Personal , it:IT-Betrieb,, ")
    assert get_processing_context_options(s) == [
        {"value": "hr", "label": "Personal"},
        {"value": "it", "label": "IT-Betrieb"},
    ]


def test_processing_context_env_entry_without_label_uses_value_as_label():
    s = _settings(processing_context_options="research,hr:Personal")
    assert get_processing_context_options(s) == [
        {"value": "research", "label": "research"},
        {"value": "hr", "label": "Personal"},
    ]


def test_processing_context_env_label_may_contain_colon():
    s = _settings(processing_context_options="x:Label: mit Doppelpunkt")
    assert get_processing_context_options(s) == [
        {"value": "x", "label": "Label: mit Doppelpunkt"}
    ]


@pytest.mark.parametrize("raw", ["   ", " , , ", ","])
def test_processing_context_env_without_entries_falls_back_to_defaults(raw: str):
    options = get_processing_context_options(_settings(processing_context_options=raw))
    assert len(options) == 7
    assert options[0] == {"value": "none", "label": "Keiner / nicht festgelegt"}
