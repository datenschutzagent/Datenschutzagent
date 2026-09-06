"""Integration tests for the Stage-5 export & gap endpoints (requires DATABASE_URL).

Covers ``app/api/routes/exports.py``:
  - GET /tom-gaps and /cases/{id}/tom-gaps
  - GET /cases/{id}/audit/export (signed CSV / JSONL)
  - GET /cases/{id}/ropa-export (CSV / DOCX)

The ROPA endpoint normalises the VVT text with the LLM; ``normalize_vvt`` is
patched at the route module so no provider is contacted.
"""

from __future__ import annotations

import csv
import io
import json
import re
import uuid
import zipfile
from unittest.mock import AsyncMock, patch

import pytest

from app.services.audit_export_service import verify_audit_signature
from app.services.vvt_service import _VVTExtractionField, _VVTExtractionResult
from tests.factories import create_case, create_tom

pytestmark = pytest.mark.asyncio

BOM = "﻿"
DOCX_CTYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


async def _add_document(
    case_id: str,
    *,
    doc_type: str = "vvt",
    content: str | None = "Zwecke: Gehaltsabrechnung",
    version: int = 1,
) -> str:
    from app.database import async_session_factory
    from app.models.db import DocumentModel

    async with async_session_factory() as session:
        doc = DocumentModel(
            case_id=uuid.UUID(case_id),
            name=f"{doc_type}-{version}.pdf",
            type=doc_type,
            version=version,
            format="pdf",
            size_bytes=10,
            storage_path=f"test/{case_id}/{doc_type}-{version}.pdf",
            content=content,
            extraction_status="completed",
        )
        session.add(doc)
        await session.commit()
        return str(doc.id)


def _extraction(*pairs: tuple[str, str | None]) -> _VVTExtractionResult:
    return _VVTExtractionResult(
        source_template="Variante A",
        fields=[
            _VVTExtractionField(
                field_name=name,
                status="filled" if value else "missing",
                canonical_value=value,
            )
            for name, value in pairs
        ],
    )


def _patch_normalize(result: _VVTExtractionResult):
    """Return (patcher, mock) replacing the LLM-backed VVT normalisation."""
    mock = AsyncMock(return_value=result)
    return patch("app.api.routes.exports.normalize_vvt", mock), mock


# ---------------------------------------------------------------------------
# TOM-Gaps
# ---------------------------------------------------------------------------


def _requirement(body: dict, req_id: str) -> dict:
    return next(r for r in body["requirements"] if r["id"] == req_id)


async def test_global_tom_gaps_reports_baseline_coverage(client):
    title = f"Verschlüsselung ruhender Daten {uuid.uuid4()}"
    await create_tom(client, title=title, category="encryption")

    resp = await client.get("/api/v1/tom-gaps")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["enabled"] is True
    summary = body["summary"]
    assert summary["total"] == len(body["requirements"])
    assert summary["met"] + summary["missing"] == summary["total"]
    assert 0.0 <= summary["coverage_pct"] <= 100.0
    req = _requirement(body, "encryption_at_rest")
    assert req["met"] is True
    assert title in req["matching_toms"]


async def test_case_tom_gaps_unknown_case_returns_404(client):
    resp = await client.get(f"/api/v1/cases/{uuid.uuid4()}/tom-gaps")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Vorgang nicht gefunden"


async def test_case_tom_gaps_rejects_invalid_uuid(client):
    resp = await client.get("/api/v1/cases/not-a-uuid/tom-gaps")
    assert resp.status_code == 422


async def test_case_tom_gaps_scopes_toms_to_case_department(client):
    dept = f"DEPT-{uuid.uuid4().hex[:8]}"
    other_dept = f"DEPT-{uuid.uuid4().hex[:8]}"
    scoped_title = f"Verschlüsselung ruhender Daten {dept}"
    await create_tom(
        client, title=scoped_title, category="encryption", department_codes=[dept]
    )
    case = await create_case(client, department=dept)
    other_case = await create_case(client, department=other_dept)

    resp = await client.get(f"/api/v1/cases/{case['id']}/tom-gaps")
    assert resp.status_code == 200, resp.text
    req = _requirement(resp.json(), "encryption_at_rest")
    assert req["met"] is True
    assert scoped_title in req["matching_toms"]

    # A TOM tagged for another department is out of scope for this case.
    resp = await client.get(f"/api/v1/cases/{other_case['id']}/tom-gaps")
    assert resp.status_code == 200
    req = _requirement(resp.json(), "encryption_at_rest")
    assert scoped_title not in req["matching_toms"]


async def test_case_tom_gaps_without_department_uses_global_set(client):
    from sqlalchemy import update

    from app.database import async_session_factory
    from app.models.db import CaseModel

    dept = f"DEPT-{uuid.uuid4().hex[:8]}"
    scoped_title = f"Verschlüsselung ruhender Daten {dept}"
    await create_tom(
        client, title=scoped_title, category="encryption", department_codes=[dept]
    )
    # The API enforces a non-empty department; legacy rows may still be blank.
    case = await create_case(client, department="IT")
    async with async_session_factory() as session:
        await session.execute(
            update(CaseModel)
            .where(CaseModel.id == uuid.UUID(case["id"]))
            .values(department="   ")
        )
        await session.commit()

    resp = await client.get(f"/api/v1/cases/{case['id']}/tom-gaps")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["enabled"] is True
    # No department → no scoping, so even department-tagged TOMs count.
    assert scoped_title in _requirement(body, "encryption_at_rest")["matching_toms"]


# ---------------------------------------------------------------------------
# Audit-Trail-Export
# ---------------------------------------------------------------------------


async def test_audit_export_unknown_case_returns_404(client):
    resp = await client.get(f"/api/v1/cases/{uuid.uuid4()}/audit/export")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Vorgang nicht gefunden"


async def test_audit_export_rejects_unknown_format(client):
    case = await create_case(client)
    resp = await client.get(
        f"/api/v1/cases/{case['id']}/audit/export", params={"format": "xml"}
    )
    assert resp.status_code == 422


async def test_audit_export_csv_default_is_signed(client):
    case = await create_case(client, title="Audit Fall: Ärger & Co")
    case_id = case["id"]

    resp = await client.get(f"/api/v1/cases/{case_id}/audit/export")
    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"].startswith("text/csv")
    disposition = resp.headers["content-disposition"]
    short_id = uuid.UUID(case_id).hex[:8]
    assert (
        disposition
        == f'attachment; filename="audit_Audit_Fall__Ärger___Co_{short_id}.csv"'
    )
    assert resp.headers["x-audit-signature-alg"] == "HMAC-SHA256"
    assert verify_audit_signature(resp.content, resp.headers["x-audit-signature"])
    assert not verify_audit_signature(
        resp.content + b"tampered", resp.headers["x-audit-signature"]
    )

    text = resp.content.decode("utf-8")
    assert text.startswith(BOM)
    rows = list(csv.reader(io.StringIO(text[len(BOM) :])))
    assert rows[0] == ["id", "event_type", "payload", "created_at"]
    for row in rows[1:]:
        uuid.UUID(row[0])
        json.loads(row[2])


async def test_audit_export_jsonl_emits_one_object_per_line(client):
    case = await create_case(client)
    case_id = case["id"]

    resp = await client.get(
        f"/api/v1/cases/{case_id}/audit/export", params={"format": "jsonl"}
    )
    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"].startswith("application/x-ndjson")
    assert resp.headers["content-disposition"].endswith(
        f'{uuid.UUID(case_id).hex[:8]}.jsonl"'
    )
    assert verify_audit_signature(resp.content, resp.headers["x-audit-signature"])

    body = resp.content.decode("utf-8")
    lines = [ln for ln in body.split("\n") if ln]
    if lines:
        assert body.endswith("\n")
    for line in lines:
        obj = json.loads(line)
        assert set(obj) == {"id", "event_type", "payload", "created_at"}
    else:
        assert body == ""


async def test_audit_export_filename_truncates_long_titles(client):
    case = await create_case(client, title="A" * 80)
    resp = await client.get(f"/api/v1/cases/{case['id']}/audit/export")
    assert resp.status_code == 200
    match = re.search(r'filename="audit_(A+)_', resp.headers["content-disposition"])
    assert match and len(match.group(1)) == 40


# ---------------------------------------------------------------------------
# ROPA-Export
# ---------------------------------------------------------------------------


async def test_ropa_export_unknown_case_returns_404(client):
    resp = await client.get(f"/api/v1/cases/{uuid.uuid4()}/ropa-export")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Vorgang nicht gefunden"


async def test_ropa_export_rejects_unknown_format(client):
    case = await create_case(client)
    resp = await client.get(
        f"/api/v1/cases/{case['id']}/ropa-export", params={"format": "pdf"}
    )
    assert resp.status_code == 422


async def test_ropa_export_rejects_invalid_document_id(client):
    case = await create_case(client)
    resp = await client.get(
        f"/api/v1/cases/{case['id']}/ropa-export", params={"document_id": "abc"}
    )
    assert resp.status_code == 422


async def test_ropa_export_without_vvt_document_returns_404(client):
    case = await create_case(client)
    await _add_document(case["id"], doc_type="other")

    resp = await client.get(f"/api/v1/cases/{case['id']}/ropa-export")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Kein VVT-Dokument für diesen Vorgang"


async def test_ropa_export_unknown_document_id_returns_404(client):
    case = await create_case(client)
    await _add_document(case["id"])

    resp = await client.get(
        f"/api/v1/cases/{case['id']}/ropa-export",
        params={"document_id": str(uuid.uuid4())},
    )
    assert resp.status_code == 404
    assert resp.json()["detail"] == "VVT-Dokument nicht gefunden"


async def test_ropa_export_document_without_content_returns_404(client):
    case = await create_case(client)
    await _add_document(case["id"], content="   \n")

    resp = await client.get(f"/api/v1/cases/{case['id']}/ropa-export")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "VVT-Dokument hat keinen extrahierten Inhalt"


async def test_ropa_export_csv_renders_vvt_fields(client):
    case = await create_case(
        client, title="Lohnbuchhaltung", department="HR", international_transfer=True
    )
    await _add_document(case["id"], content="VVT-Text Lohn")
    patcher, mock = _patch_normalize(
        _extraction(
            ("Zwecke der Verarbeitung", "Gehaltsabrechnung"),
            ("Löschfristen", "10 Jahre"),
            ("Kategorien betroffener Personen", None),
        )
    )
    with patcher:
        resp = await client.get(f"/api/v1/cases/{case['id']}/ropa-export")

    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"].startswith("text/csv")
    short_id = uuid.UUID(case["id"]).hex[:8]
    filename = f"ROPA_Lohnbuchhaltung_{short_id}.csv"
    assert resp.headers["content-disposition"] == (
        f"attachment; filename=\"{filename}\"; filename*=UTF-8''{filename}"
    )
    mock.assert_awaited_once()
    assert mock.await_args.args == ("VVT-Text Lohn",)
    assert mock.await_args.kwargs["language"] == "de"
    assert isinstance(mock.await_args.kwargs["field_names"], list)

    text = resp.content.decode("utf-8")
    assert text.startswith(BOM)
    rows = list(csv.reader(io.StringIO(text[len(BOM) :])))
    assert rows[0] == ["Abschnitt", "Inhalt", "Quelle"]
    by_label = {r[0]: r for r in rows[1:] if r}
    assert by_label["3. Zwecke der Verarbeitung"][1:] == ["Gehaltsabrechnung", "vvt"]
    assert by_label["9. Geplante Fristen für die Löschung"][1:] == ["10 Jahre", "vvt"]
    assert by_label["5. Kategorien betroffener Personen"][1:] == [
        "— (im VVT-Dokument nicht erfasst)",
        "missing",
    ]
    assert by_label["8. Übermittlung in Drittländer / int. Organisationen"][1:] == [
        "Ja",
        "case",
    ]
    assert by_label["Vorgang"][1] == "Lohnbuchhaltung"
    assert by_label["Abteilung"][1] == "HR"


async def test_ropa_export_docx_contains_case_and_field_values(client):
    case = await create_case(client, title="Bewerber Portal", department="HR")
    await _add_document(case["id"])
    patcher, _ = _patch_normalize(
        _extraction(("Rechtsgrundlage", "Art. 6 Abs. 1 lit. b DSGVO"))
    )
    with patcher:
        resp = await client.get(
            f"/api/v1/cases/{case['id']}/ropa-export", params={"format": "docx"}
        )

    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"] == DOCX_CTYPE
    short_id = uuid.UUID(case["id"]).hex[:8]
    assert (
        f'filename="ROPA_Bewerber_Portal_{short_id}.docx"'
        in resp.headers["content-disposition"]
    )

    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        xml = zf.read("word/document.xml").decode("utf-8")
    assert "Verzeichnis von Verarbeitungstätigkeiten" in xml
    assert "Bewerber Portal" in xml
    assert "Art. 6 Abs. 1 lit. b DSGVO" in xml
    assert "Abschnitt nach Art. 30 DSGVO" in xml


async def test_ropa_export_document_id_selects_specific_vvt_document(client):
    case = await create_case(client)
    await _add_document(case["id"], content="erste Variante", version=1)
    second = await _add_document(case["id"], content="zweite Variante", version=2)
    patcher, mock = _patch_normalize(_extraction())
    with patcher:
        resp = await client.get(
            f"/api/v1/cases/{case['id']}/ropa-export",
            params={"document_id": second},
        )

    assert resp.status_code == 200, resp.text
    assert mock.await_args.args == ("zweite Variante",)


async def test_ropa_export_filename_encodes_non_ascii_title(client):
    case = await create_case(client, title="Übergabe/Ärzte")
    await _add_document(case["id"])
    patcher, _ = _patch_normalize(_extraction())
    with patcher:
        resp = await client.get(f"/api/v1/cases/{case['id']}/ropa-export")

    assert resp.status_code == 200, resp.text
    disposition = resp.headers["content-disposition"]
    assert 'filename="ROPA_Übergabe_Ärzte_' in disposition
    assert "filename*=UTF-8''ROPA_%C3%9Cbergabe_%C3%84rzte_" in disposition
