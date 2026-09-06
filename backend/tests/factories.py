"""Entity factories for API tests.

Each helper POSTs a valid default payload through the public API and returns the
response body. Override any field via keyword arguments::

    case = await create_case(client, title="Mein Vorgang", department="HR")

They replace the copies of ``_create_case``/``_create_avv``/… that every API test
module used to carry (Qualitätsplan Phase 4, T2). Keep defaults boring: tests that
depend on a specific value must pass it explicitly.
"""

from __future__ import annotations

from typing import Any

from httpx import AsyncClient


async def _post(client: AsyncClient, path: str, payload: dict[str, Any]) -> dict:
    resp = await client.post(path, json=payload)
    assert resp.status_code == 201, f"{path}: {resp.status_code} {resp.text}"
    return resp.json()


async def create_case(client: AsyncClient, **overrides: Any) -> dict:
    payload: dict[str, Any] = {
        "title": "Test-Vorgang",
        "department": "IT",
        "case_type": "Softwareeinführung",
        "language": "de",
        "created_by": "test@example.com",
        "assignee": "DSB Team",
        "processing_context": None,
        "special_category_data": False,
        "international_transfer": False,
        **overrides,
    }
    return await _post(client, "/api/v1/cases", payload)


async def create_avv(client: AsyncClient, **overrides: Any) -> dict:
    payload: dict[str, Any] = {
        "partner_name": "Cloud Corp GmbH",
        "partner_type": "processor",
        "subject_matter": "Cloud-Hosting",
        "department": "IT",
        "assignee": "DSB Team",
        "contract_date": "2026-01-01",
        "expiry_date": "2027-01-01",
        "notes": "Jährliche Verlängerung",
        **overrides,
    }
    return await _post(client, "/api/v1/avv", payload)


async def create_dsr(client: AsyncClient, **overrides: Any) -> dict:
    payload: dict[str, Any] = {
        "request_type": "access",
        "requestor_name": "Max Mustermann",
        "requestor_email": "max@example.com",
        "description": "Auskunft über gespeicherte Daten",
        "department": "IT",
        "assignee": "DSB Team",
        "received_at": "2026-04-14",
        "deadline_extension_days": 0,
        **overrides,
    }
    return await _post(client, "/api/v1/dsr", payload)


async def create_tom(client: AsyncClient, **overrides: Any) -> dict:
    payload: dict[str, Any] = {
        "title": "Verschlüsselung ruhender Daten",
        "description": "AES-256 Verschlüsselung für Datenbanken",
        "category": "encryption",
        "implementation_status": "implemented",
        "responsible": "IT-Sicherheit",
        "evidence": "Dokumentiert in IT-Richtlinie §5",
        **overrides,
    }
    return await _post(client, "/api/v1/tom", payload)


async def create_breach(client: AsyncClient, **overrides: Any) -> dict:
    payload: dict[str, Any] = {
        "title": "Testdatenpanne",
        "description": "E-Mail-Versand an falschen Empfänger",
        "discovered_at": "2026-04-14T10:00:00",
        "breach_type": "confidentiality",
        "affected_data_categories": ["name", "email"],
        "affected_persons_count": 50,
        "department": "HR",
        "assignee": "DSB Team",
        "risk_level": "medium",
        **overrides,
    }
    return await _post(client, "/api/v1/data-breaches", payload)
