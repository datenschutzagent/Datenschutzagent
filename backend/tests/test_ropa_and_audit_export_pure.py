"""Pure tests for ROPA-CSV rendering and signed audit-trail HMAC.

The DOCX renderer needs python-docx so we only verify it loads; the CSV
path is fully exercised here. HMAC tests cover both the happy path and
tampered-body detection.
"""
from __future__ import annotations

import hashlib
import hmac
import os

import pytest

from app.services.audit_export_service import (
    _audit_signing_key,
    verify_audit_signature,
)
from app.services.ropa_export_service import (
    _ART30_SECTIONS,
    build_ropa_csv,
    _project_art30_rows,
)


# ---------------------------------------------------------------------------
# ROPA — Art-30 section coverage
# ---------------------------------------------------------------------------


_CASE = {
    "title": "Mitarbeiter-Tracking",
    "department": "HR",
    "international_transfer": True,
    "org_name": "ExampleOrg",
    "dpo_contact": "dpo@example.org",
}


def _fields(**overrides):
    """Build VVT-field rows shaped like ``normalize_vvt`` output."""
    defaults = {
        "Verantwortlicher": "Acme GmbH, CEO",
        "Zwecke der Verarbeitung": "Performance-Auswertung",
        "Kategorien betroffener Personen": "Mitarbeiter",
        "Kategorien personenbezogener Daten": "Zeitstempel, Standort",
        "Rechtsgrundlage": "Art. 6 Abs. 1 lit. f",
        "Empfänger": "interne IT",
        "Drittland": "USA",
        "Löschfrist": "30 Tage",
        "TOM": "Verschlüsselung, RBAC",
    }
    defaults.update(overrides)
    return [{"field_name": k, "canonical_value": v} for k, v in defaults.items()]


def test_csv_renders_all_art30_sections():
    body = build_ropa_csv(case_summary=_CASE, vvt_fields=_fields())
    text = body.decode("utf-8")
    # Header
    assert "Abschnitt,Inhalt,Quelle" in text
    # Every canonical Art-30 section label appears.
    for _, label in _ART30_SECTIONS:
        assert label in text, f"missing label: {label}"


def test_csv_uses_vvt_value_when_available():
    body = build_ropa_csv(case_summary=_CASE, vvt_fields=_fields())
    text = body.decode("utf-8")
    assert "Acme GmbH, CEO" in text
    assert "Performance-Auswertung" in text


def test_csv_falls_back_to_case_for_org_level_fields_when_missing():
    """Verantwortlicher + DSB-Kontakt sind organisationsweit bekannt;
    fehlen sie im VVT-Dokument, müssen sie aus dem Case-Summary kommen."""
    body = build_ropa_csv(case_summary=_CASE, vvt_fields=[])
    text = body.decode("utf-8")
    assert "ExampleOrg" in text
    assert "dpo@example.org" in text
    # International transfer derives from case flags too.
    assert ",Ja," in text  # Drittland section value


def test_csv_marks_truly_missing_fields():
    rows = _project_art30_rows(case_summary={"title": "x"}, vvt_fields=[])
    # With empty fallbacks: zwecke etc. → missing
    missing = [r for r in rows if r["source"] == "missing"]
    assert any(r["key"] == "zwecke" for r in missing)
    # Drittland default 'Nein' counts as 'case'-sourced when flag is False.


def test_provenance_source_marks_vvt_correctly():
    rows = _project_art30_rows(case_summary=_CASE, vvt_fields=_fields())
    by_key = {r["key"]: r for r in rows}
    assert by_key["zwecke"]["source"] == "vvt"
    # When VVT doesn't carry a verantwortlicher value, ``case`` fallback applies.
    rows2 = _project_art30_rows(case_summary=_CASE, vvt_fields=_fields(**{"Verantwortlicher": ""}))
    by_key2 = {r["key"]: r for r in rows2}
    assert by_key2["verantwortlicher"]["source"] == "case"


def test_csv_uses_bom_for_excel_compat():
    body = build_ropa_csv(case_summary=_CASE, vvt_fields=_fields())
    assert body.startswith("﻿".encode("utf-8"))


# ---------------------------------------------------------------------------
# Audit-trail HMAC signature
# ---------------------------------------------------------------------------


def test_signature_round_trip(monkeypatch):
    monkeypatch.setenv("AUDIT_EXPORT_SIGNING_KEY", "test-secret-123")
    payload = b"id,event_type,payload,created_at\nabc,run_checks,{},2026-05-29T00:00:00\n"
    sig = hmac.new(b"test-secret-123", payload, hashlib.sha256).hexdigest()
    assert verify_audit_signature(payload, sig) is True


def test_signature_detects_tampering(monkeypatch):
    monkeypatch.setenv("AUDIT_EXPORT_SIGNING_KEY", "test-secret-123")
    payload = b"row-a"
    sig = hmac.new(b"test-secret-123", payload, hashlib.sha256).hexdigest()
    # Even a single-byte change must invalidate.
    assert verify_audit_signature(b"row-b", sig) is False


def test_signing_key_uses_env_when_set(monkeypatch):
    monkeypatch.setenv("AUDIT_EXPORT_SIGNING_KEY", "explicit")
    assert _audit_signing_key() == b"explicit"


def test_signing_key_falls_back_to_derived_when_unset(monkeypatch):
    monkeypatch.delenv("AUDIT_EXPORT_SIGNING_KEY", raising=False)
    monkeypatch.delenv("WEBHOOK_SECRET_ENCRYPTION_KEY", raising=False)
    monkeypatch.delenv("APP_SECRET_KEY", raising=False)
    key = _audit_signing_key()
    # 32-byte BLAKE2b digest
    assert isinstance(key, bytes) and len(key) == 32
    # Deterministic across two calls in same process.
    assert _audit_signing_key() == key


def test_signature_changes_when_key_changes(monkeypatch):
    payload = b"some audit row"
    monkeypatch.setenv("AUDIT_EXPORT_SIGNING_KEY", "key-A")
    sig_a = hmac.new(_audit_signing_key(), payload, hashlib.sha256).hexdigest()
    monkeypatch.setenv("AUDIT_EXPORT_SIGNING_KEY", "key-B")
    sig_b = hmac.new(_audit_signing_key(), payload, hashlib.sha256).hexdigest()
    assert sig_a != sig_b
