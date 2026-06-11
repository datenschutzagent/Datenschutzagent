"""Unit tests for pure helper functions in playbook_import.py.

Tests _normalize_check_scope(), _yaml_to_model_data(), and _load_playbook_yaml()
with no database required. Uses pytest's tmp_path fixture for file I/O tests.
"""

from app.services.playbook_import import (
    _load_playbook_yaml,
    _normalize_check_scope,
    _yaml_to_model_data,
)

# ---------------------------------------------------------------------------
# _normalize_check_scope
# ---------------------------------------------------------------------------


def test_scope_case_stays_case():
    result = _normalize_check_scope({"scope": "case", "name": "Check A"})
    assert result["scope"] == "case"


def test_scope_cross_document_normalizes_to_case():
    result = _normalize_check_scope({"scope": "cross_document", "name": "Check B"})
    assert result["scope"] == "case"


def test_scope_document_stays_document():
    result = _normalize_check_scope({"scope": "document", "name": "Check C"})
    assert result["scope"] == "document"


def test_scope_missing_defaults_to_document():
    result = _normalize_check_scope({"name": "Check D"})
    assert result["scope"] == "document"


def test_scope_unknown_value_normalizes_to_document():
    result = _normalize_check_scope({"scope": "unknown_value"})
    assert result["scope"] == "document"


def test_scope_type_field_used_when_scope_missing():
    result = _normalize_check_scope({"type": "case"})
    assert result["scope"] == "case"


def test_scope_scope_takes_precedence_over_type():
    result = _normalize_check_scope({"scope": "document", "type": "case"})
    assert result["scope"] == "document"


def test_normalize_preserves_other_fields():
    item = {
        "scope": "case",
        "name": "My Check",
        "instruction": "Do something",
        "priority": 5,
    }
    result = _normalize_check_scope(item)
    assert result["name"] == "My Check"
    assert result["instruction"] == "Do something"
    assert result["priority"] == 5


# ---------------------------------------------------------------------------
# _yaml_to_model_data
# ---------------------------------------------------------------------------


def test_yaml_to_model_data_minimal_valid():
    data = {"name": "My Playbook", "version": "1.0", "checks": []}
    result = _yaml_to_model_data(data)
    assert result is not None
    assert result["name"] == "My Playbook"
    assert result["version"] == "1.0"
    assert result["content"]["checks"] == []
    assert result["is_active"] is True


def test_yaml_to_model_data_missing_name_returns_none():
    data = {"version": "1.0", "checks": []}
    assert _yaml_to_model_data(data) is None


def test_yaml_to_model_data_missing_version_returns_none():
    data = {"name": "My Playbook", "checks": []}
    assert _yaml_to_model_data(data) is None


def test_yaml_to_model_data_empty_dict_returns_none():
    assert _yaml_to_model_data({}) is None


def test_yaml_to_model_data_checks_not_list_defaults_to_empty():
    data = {"name": "PB", "version": "1.0", "checks": "not_a_list"}
    result = _yaml_to_model_data(data)
    assert result is not None
    assert result["content"]["checks"] == []


def test_yaml_to_model_data_checks_none_defaults_to_empty():
    data = {"name": "PB", "version": "1.0", "checks": None}
    result = _yaml_to_model_data(data)
    assert result is not None
    assert result["content"]["checks"] == []


def test_yaml_to_model_data_normalizes_check_scopes():
    data = {
        "name": "PB",
        "version": "1.0",
        "checks": [
            {"name": "A", "scope": "cross_document"},
            {"name": "B", "scope": "document"},
        ],
    }
    result = _yaml_to_model_data(data)
    assert result is not None
    checks = result["content"]["checks"]
    assert checks[0]["scope"] == "case"
    assert checks[1]["scope"] == "document"


def test_yaml_to_model_data_legal_basis_ids_converted_to_strings():
    import uuid as _uuid

    uid = _uuid.uuid4()
    data = {
        "name": "PB",
        "version": "1.0",
        "checks": [],
        "legal_basis_ids": [uid, "some-string-id"],
    }
    result = _yaml_to_model_data(data)
    assert result is not None
    ids = result["content"]["legal_basis_ids"]
    assert all(isinstance(i, str) for i in ids)


def test_yaml_to_model_data_legal_basis_ids_not_list_ignored():
    data = {
        "name": "PB",
        "version": "1.0",
        "checks": [],
        "legal_basis_ids": "not-a-list",
    }
    result = _yaml_to_model_data(data)
    assert result is not None
    assert "legal_basis_ids" not in result["content"]


def test_yaml_to_model_data_match_cfg_preserved():
    data = {
        "name": "PB",
        "version": "1.0",
        "checks": [],
        "match": {"priority": 10, "department_values": ["IT"]},
    }
    result = _yaml_to_model_data(data)
    assert result is not None
    assert result["content"]["match"] == {"priority": 10, "department_values": ["IT"]}


def test_yaml_to_model_data_department_and_case_type():
    data = {
        "name": "PB",
        "version": "1.0",
        "checks": [],
        "department": "IT",
        "case_type": "Software",
    }
    result = _yaml_to_model_data(data)
    assert result is not None
    assert result["department"] == "IT"
    assert result["case_type"] == "Software"


def test_yaml_to_model_data_version_coerced_to_string():
    data = {"name": "PB", "version": 2, "checks": []}
    result = _yaml_to_model_data(data)
    assert result is not None
    assert result["version"] == "2"


# ---------------------------------------------------------------------------
# _load_playbook_yaml
# ---------------------------------------------------------------------------


def test_load_playbook_yaml_valid_file(tmp_path):
    f = tmp_path / "playbook.yaml"
    f.write_text("name: Test\nversion: '1.0'\nchecks: []\n", encoding="utf-8")
    result = _load_playbook_yaml(f)
    assert result is not None
    assert result["name"] == "Test"


def test_load_playbook_yaml_yml_extension(tmp_path):
    f = tmp_path / "playbook.yml"
    f.write_text("name: Another\nversion: '2.0'\nchecks: []\n", encoding="utf-8")
    result = _load_playbook_yaml(f)
    assert result is not None
    assert result["name"] == "Another"


def test_load_playbook_yaml_non_yaml_extension_returns_none(tmp_path):
    f = tmp_path / "playbook.txt"
    f.write_text("name: Test\n", encoding="utf-8")
    result = _load_playbook_yaml(f)
    assert result is None


def test_load_playbook_yaml_non_dict_root_returns_none(tmp_path):
    f = tmp_path / "playbook.yaml"
    f.write_text("- item1\n- item2\n", encoding="utf-8")
    result = _load_playbook_yaml(f)
    assert result is None


def test_load_playbook_yaml_malformed_yaml_returns_none(tmp_path):
    f = tmp_path / "broken.yaml"
    f.write_text("{invalid: yaml: content: [}", encoding="utf-8")
    result = _load_playbook_yaml(f)
    assert result is None


def test_load_playbook_yaml_nonexistent_file_returns_none(tmp_path):
    f = tmp_path / "does_not_exist.yaml"
    result = _load_playbook_yaml(f)
    assert result is None
