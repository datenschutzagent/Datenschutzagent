"""Score playbooks against case attributes (department, processing context, case type, org profile)."""
from typing import Any

from app.models.db import PlaybookModel


def _match_spec(playbook: PlaybookModel) -> dict[str, Any]:
    content = playbook.content if isinstance(playbook.content, dict) else {}
    spec = content.get("match")
    if isinstance(spec, dict) and spec:
        return dict(spec)
    return _legacy_spec(playbook)


def _legacy_spec(playbook: PlaybookModel) -> dict[str, Any]:
    spec: dict[str, Any] = {"priority": 0}
    if playbook.department:
        spec["department_values"] = [playbook.department]
    else:
        spec["department_values"] = []
    spec["department_codes"] = []
    return spec


def _department_ok(case_department: str, spec: dict[str, Any]) -> bool:
    dvals = spec.get("department_values") or []
    if not isinstance(dvals, list):
        dvals = []
    dvals = [str(v) for v in dvals if v is not None and str(v).strip()]
    dcodes = spec.get("department_codes") or []
    if not isinstance(dcodes, list):
        dcodes = []
    dcodes = [str(c).strip() for c in dcodes if c is not None and str(c).strip()]

    if dvals and case_department not in dvals:
        return False
    if dcodes:
        ok = False
        for c in dcodes:
            if case_department == c or case_department.startswith(f"{c} –") or case_department.startswith(f"{c} "):
                ok = True
                break
        if not ok:
            return False
    return True


def _processing_ok(processing_context: str | None, spec: dict[str, Any]) -> bool:
    pcs = spec.get("processing_contexts")
    if not pcs or not isinstance(pcs, list):
        return True
    norm = [str(p) for p in pcs if p is not None and str(p).strip()]
    if not norm:
        return True
    if processing_context is None or not str(processing_context).strip():
        return False
    return processing_context in norm


def _org_profile_ok(org_profile: str, spec: dict[str, Any]) -> bool:
    ops = spec.get("org_profiles")
    if not ops or not isinstance(ops, list):
        return True
    norm = [str(o) for o in ops if o is not None and str(o).strip()]
    if not norm:
        return True
    return org_profile in norm


def _case_type_ok(case_type: str | None, spec: dict[str, Any], *, strict: bool) -> bool:
    cts = spec.get("case_types")
    if not cts or not isinstance(cts, list):
        return True
    norm = [str(t) for t in cts if t is not None and str(t).strip()]
    if not norm:
        return True
    ct = (case_type or "").strip()
    if not ct:
        return not strict
    return ct in norm


def playbook_selection_priority(
    playbook: PlaybookModel,
    *,
    department: str,
    processing_context: str | None = None,
    case_type: str | None = None,
    org_profile: str = "default",
    strict_case_type: bool = False,
) -> int | None:
    """
    Return match priority (higher = more specific) if the playbook applies, else None.
    When strict_case_type is False (e.g. new-case wizard before case type chosen), case_types in match are ignored.
    When True, non-empty case_types in match require the given case_type to be listed.
    """
    if not playbook.is_active:
        return None
    spec = _match_spec(playbook)
    if not _department_ok(department, spec):
        return None
    if not _processing_ok(processing_context, spec):
        return None
    if not _org_profile_ok(org_profile, spec):
        return None
    if not _case_type_ok(case_type, spec, strict=strict_case_type):
        return None
    try:
        return int(spec.get("priority", 0))
    except (TypeError, ValueError):
        return 0


def rank_playbooks_for_selection(
    playbooks: list[PlaybookModel],
    *,
    department: str,
    processing_context: str | None = None,
    case_type: str | None = None,
    org_profile: str = "default",
    strict_case_type: bool = False,
) -> list[tuple[PlaybookModel, int]]:
    """Return (playbook, priority) pairs that match, sorted by priority descending then name."""
    ranked: list[tuple[PlaybookModel, int]] = []
    for pb in playbooks:
        pr = playbook_selection_priority(
            pb,
            department=department,
            processing_context=processing_context,
            case_type=case_type,
            org_profile=org_profile,
            strict_case_type=strict_case_type,
        )
        if pr is not None:
            ranked.append((pb, pr))
    ranked.sort(key=lambda x: (-x[1], x[0].name or ""))
    return ranked
