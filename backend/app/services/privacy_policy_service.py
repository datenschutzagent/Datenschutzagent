"""Datenschutzerklärung-Generator: Erstellt Website-Datenschutzerklärungen aus VVT-Daten.

Generiert eine rechtlich strukturierte Datenschutzerklärung (DSGVO Art. 13/14)
auf Basis der VVT-Übersicht und des Organisations-Profils.
"""
import logging
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.llm import create_agent
from app.core.prompt_security import sanitize_prompt_field
from app.models.db import PrivacyPolicyModel

logger = logging.getLogger(__name__)


_PRIVACY_POLICY_SYSTEM = """Du bist ein erfahrener Datenschutzjurist in Deutschland.
Erstelle eine rechtskonforme Datenschutzerklärung gemäß Art. 13/14 DSGVO für eine Website.
Die Erklärung muss folgende Pflichtangaben enthalten:
1. Verantwortlicher (Name, Adresse, Kontakt)
2. Datenschutzbeauftragter (falls vorhanden)
3. Verarbeitungszwecke und Rechtsgrundlagen (Art. 6 DSGVO)
4. Kategorien personenbezogener Daten
5. Empfänger / Auftragsverarbeiter
6. Speicherdauer / Löschfristen
7. Betroffenenrechte (Art. 15-22 DSGVO)
8. Beschwerderecht bei Aufsichtsbehörde
9. Hinweise zu Cookies und Tracking (falls zutreffend)
Schreibe klar, verständlich und rechtssicher. Antworte auf Deutsch."""


_PRIVACY_POLICY_USER_TEMPLATE = """Erstelle eine Datenschutzerklärung für folgende Organisation:

**Organisation**: {org_name}
**Abteilung/Bereich**: {department}
**Kontakt (Verantwortlicher)**: {contact}

**Verarbeitungstätigkeiten aus dem VVT (Art. 30 DSGVO)**:
{vvt_summary}

**Auftragsverarbeiter (AVV)**:
{avv_summary}

**Besondere Hinweise**:
{notes}

Erstelle eine vollständige, strukturierte Datenschutzerklärung als Markdown-Dokument.
Füge Platzhalter [DATUM] und [KONTAKT] ein, wo konkrete Angaben fehlen."""


class _PrivacyPolicyLLMResult(BaseModel):
    title: str = Field(description="Titel der Datenschutzerklärung")
    content_markdown: str = Field(description="Vollständige Datenschutzerklärung als Markdown")
    version_note: str = Field(description="Kurze Notiz zur Version / zu Änderungen")


async def generate_privacy_policy(
    db: AsyncSession,
    org_name: str,
    department: str = "",
    contact: str = "",
    notes: str = "",
) -> dict[str, Any]:
    """Generiert eine Datenschutzerklärung und gibt das Payload-Dict zurück."""
    from app.config import settings

    # VVT-Zusammenfassung aus vorhandenen Cases laden
    vvt_summary = await _build_vvt_summary(db, department)

    # AVV-Zusammenfassung
    avv_summary = await _build_avv_summary(db)

    org = org_name or settings.org_name or "Ihre Organisation"

    user_content = _PRIVACY_POLICY_USER_TEMPLATE.format(
        org_name=sanitize_prompt_field(org, max_chars=200),
        department=sanitize_prompt_field(department or "Gesamte Organisation", max_chars=200),
        contact=sanitize_prompt_field(contact or "[Kontaktdaten des Verantwortlichen eintragen]", max_chars=500),
        vvt_summary=sanitize_prompt_field(vvt_summary, max_chars=4000),
        avv_summary=sanitize_prompt_field(avv_summary, max_chars=2000),
        notes=sanitize_prompt_field(notes or "Keine besonderen Hinweise.", max_chars=1000),
    )

    agent = create_agent(_PRIVACY_POLICY_SYSTEM)
    result = await agent.run(user_content, output_type=_PrivacyPolicyLLMResult)
    data = result.output

    return {
        "title": data.title,
        "content_markdown": data.content_markdown,
        "version_note": data.version_note,
        "org_name": org,
        "department": department,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


async def _build_vvt_summary(db: AsyncSession, department: str = "") -> str:
    """Baut eine kompakte VVT-Zusammenfassung für den LLM-Prompt."""
    from app.models.db import CaseModel
    q = select(CaseModel).where(CaseModel.archived_at == None)  # noqa: E711
    if department:
        q = q.where(CaseModel.department.ilike(f"%{department}%"))
    q = q.order_by(CaseModel.updated_at.desc()).limit(20)
    result = await db.execute(q)
    cases = result.scalars().all()
    if not cases:
        return "Keine Verarbeitungstätigkeiten im VVT erfasst."
    lines = []
    for case in cases:
        extras = []
        if case.special_category_data:
            extras.append("Art.-9-Daten")
        if case.international_transfer:
            extras.append("Drittlandtransfer")
        line = f"- {case.title} (Abteilung: {case.department}, Typ: {case.case_type})"
        if extras:
            line += f" [{', '.join(extras)}]"
        lines.append(line)
    return "\n".join(lines)


async def _build_avv_summary(db: AsyncSession) -> str:
    """Baut eine kompakte AVV-Zusammenfassung für den LLM-Prompt."""
    from app.models.db import AVVContractModel
    result = await db.execute(
        select(AVVContractModel)
        .where(AVVContractModel.status == "signed")
        .order_by(AVVContractModel.partner_name.asc())
        .limit(20)
    )
    contracts = result.scalars().all()
    if not contracts:
        return "Keine unterzeichneten AVV vorhanden."
    lines = []
    for c in contracts:
        type_label = "AV" if c.partner_type == "processor" else "Unter-AV"
        line = f"- {c.partner_name} ({type_label})"
        if c.subject_matter:
            line += f": {c.subject_matter[:80]}"
        lines.append(line)
    return "\n".join(lines)


async def save_privacy_policy(
    db: AsyncSession,
    payload: dict[str, Any],
    created_by: str = "",
) -> "PrivacyPolicyModel":
    """Persistiert eine generierte Datenschutzerklärung."""
    model = PrivacyPolicyModel(
        title=payload.get("title", "Datenschutzerklärung"),
        content_markdown=payload.get("content_markdown", ""),
        version_note=payload.get("version_note", ""),
        org_name=payload.get("org_name", ""),
        department=payload.get("department", ""),
        payload=payload,
        generated_at=datetime.now(timezone.utc),
        created_by=created_by,
    )
    db.add(model)
    await db.flush()
    await db.refresh(model)
    return model


async def list_privacy_policies(db: AsyncSession) -> list["PrivacyPolicyModel"]:
    """Gibt alle gespeicherten Datenschutzerklärungen zurück."""
    result = await db.execute(
        select(PrivacyPolicyModel).order_by(PrivacyPolicyModel.generated_at.desc())
    )
    return result.scalars().all()
