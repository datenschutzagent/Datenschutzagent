"""Datenschutzerklaerung-Generator: Erstellt vorgangsspezifische
Datenschutzerklaerungen aus Case-Daten.

Eine Erklaerung beschreibt **eine konkrete Verarbeitungstaetigkeit** (einen
Case) gemaess Art. 13/14 DSGVO. Die Generierung nutzt:

- Case-Stammdaten (Titel, Abteilung, Typ, Verarbeitungs-Kontext, Art.-9,
  Drittlandtransfer, Speicherfristen)
- Findings des Cases als Hinweise auf bekannte Schwachstellen
- AVV-Vertraege der gleichen Abteilung (best-effort)
- Org-Profil (Name) aus Settings
"""

import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.llm import create_agent, wrap_output_type
from app.core.prompt_security import sanitize_prompt_field
from app.models.db import (
    AVVContractModel,
    CaseModel,
    FindingModel,
    PrivacyPolicyModel,
)

logger = logging.getLogger(__name__)


_PRIVACY_POLICY_SYSTEM = """Du bist ein erfahrener Datenschutzjurist in Deutschland.
Erstelle eine rechtskonforme Datenschutzerklärung gemäß Art. 13/14 DSGVO für eine
**konkrete Verarbeitungstätigkeit** (einen Vorgang). Die Erklärung muss folgende
Pflichtangaben enthalten:
1. Verantwortlicher (Name, Adresse, Kontakt)
2. Datenschutzbeauftragter (falls vorhanden)
3. Verarbeitungszweck und Rechtsgrundlage (Art. 6 DSGVO) für genau diese Tätigkeit
4. Kategorien personenbezogener Daten in dieser Verarbeitung
5. Empfänger / Auftragsverarbeiter (sofern relevant für diese Tätigkeit)
6. Speicherdauer / Löschfristen für diese Verarbeitung
7. Betroffenenrechte (Art. 15-22 DSGVO)
8. Beschwerderecht bei Aufsichtsbehörde
9. Hinweise auf besondere Datenkategorien (Art. 9) und Drittlandtransfers, falls zutreffend

Wichtig: Die Erklärung beschreibt **nur diese eine Verarbeitungstätigkeit**, keine
gesamtorganisatorische Übersicht. Schreibe klar, verständlich und rechtssicher.
Antworte auf Deutsch."""


_PRIVACY_POLICY_USER_TEMPLATE = """Erstelle eine Datenschutzerklärung für folgende Verarbeitungstätigkeit:

**Organisation**: {org_name}
**Kontakt (Verantwortlicher)**: {contact}

**Vorgang (Verarbeitungstätigkeit)**:
- Titel: {case_title}
- Abteilung/Bereich: {case_department}
- Typ: {case_type}
- Verarbeitungs-Kontext: {processing_context}
- Besondere Datenkategorien (Art. 9 DSGVO): {special_category}
- Drittlandtransfer: {international_transfer}
- Speicherdauer: {retention}

**Bekannte offene Findings/Hinweise zu dieser Verarbeitung**:
{findings_summary}

**Auftragsverarbeiter (AVV) im Bereich dieser Verarbeitung**:
{avv_summary}

**Besondere Hinweise**:
{notes}

Erstelle eine vollständige, strukturierte Datenschutzerklärung als Markdown-Dokument
**bezogen auf genau diese Verarbeitungstätigkeit**. Füge Platzhalter wie [DATUM]
oder [KONTAKT] ein, wo konkrete Angaben fehlen."""


class _PrivacyPolicyLLMResult(BaseModel):
    title: str = Field(description="Titel der Datenschutzerklärung")
    content_markdown: str = Field(
        description="Vollständige Datenschutzerklärung als Markdown"
    )
    version_note: str = Field(description="Kurze Notiz zur Version / zu Änderungen")


async def generate_privacy_policy(
    db: AsyncSession,
    case_id: UUID,
    contact: str = "",
    notes: str = "",
) -> dict[str, Any]:
    """Generiert eine Datenschutzerklärung für genau einen Case und gibt das Payload-Dict zurück.

    Wirft ``ValueError``, falls der Case nicht existiert.
    """
    from app.config import settings

    case = await db.get(CaseModel, case_id)
    if case is None:
        raise ValueError(f"Case {case_id} nicht gefunden")

    findings_summary = await _build_findings_summary(db, case_id)
    avv_summary = await _build_avv_summary(db, case.department)

    org_name = settings.org_name or "Ihre Organisation"

    retention = (
        f"{case.retention_months} Monate"
        if case.retention_months
        else "[Speicherfrist eintragen]"
    )

    user_content = _PRIVACY_POLICY_USER_TEMPLATE.format(
        org_name=sanitize_prompt_field(org_name, max_chars=200),
        contact=sanitize_prompt_field(
            contact or "[Kontaktdaten des Verantwortlichen eintragen]", max_chars=500
        ),
        case_title=sanitize_prompt_field(case.title, max_chars=300),
        case_department=sanitize_prompt_field(case.department or "—", max_chars=200),
        case_type=sanitize_prompt_field(case.case_type or "—", max_chars=100),
        processing_context=sanitize_prompt_field(
            case.processing_context or "—", max_chars=500
        ),
        special_category="Ja" if case.special_category_data else "Nein",
        international_transfer="Ja" if case.international_transfer else "Nein",
        retention=sanitize_prompt_field(retention, max_chars=100),
        findings_summary=sanitize_prompt_field(findings_summary, max_chars=3000),
        avv_summary=sanitize_prompt_field(avv_summary, max_chars=2000),
        notes=sanitize_prompt_field(
            notes or "Keine besonderen Hinweise.", max_chars=1000
        ),
    )

    agent = create_agent(_PRIVACY_POLICY_SYSTEM)
    result = await agent.run(
        user_content, output_type=wrap_output_type(_PrivacyPolicyLLMResult)
    )
    data = result.output

    return {
        "title": data.title,
        "content_markdown": data.content_markdown,
        "version_note": data.version_note,
        "case_id": str(case.id),
        "case_title": case.title,
        "case_department": case.department,
        "org_name": org_name,
        "generated_at": datetime.now(UTC).isoformat(),
    }


async def _build_findings_summary(db: AsyncSession, case_id: UUID) -> str:
    """Baut eine kompakte Findings-Zusammenfassung fuer den LLM-Prompt."""
    result = await db.execute(
        select(FindingModel)
        .where(FindingModel.case_id == case_id, FindingModel.status == "open")
        .order_by(FindingModel.severity.asc(), FindingModel.created_at.desc())
        .limit(20)
    )
    findings = result.scalars().all()
    if not findings:
        return "Keine offenen Findings."
    lines = []
    for f in findings:
        lines.append(f"- [{f.severity}] {f.check_name}: {f.description[:150]}")
    return "\n".join(lines)


async def _build_avv_summary(db: AsyncSession, department: str | None) -> str:
    """Baut eine kompakte AVV-Zusammenfassung fuer den LLM-Prompt.

    Best-effort: bevorzugt AVV der gleichen Abteilung; wenn keine vorhanden,
    Fallback auf alle signed AVV (max. 10).
    """
    q = select(AVVContractModel).where(AVVContractModel.status == "signed")
    if department:
        q_dept = q.where(AVVContractModel.department == department).limit(20)
        result = await db.execute(q_dept)
        contracts = result.scalars().all()
        if contracts:
            return _format_avv(contracts)
    result = await db.execute(q.order_by(AVVContractModel.partner_name.asc()).limit(10))
    contracts = result.scalars().all()
    if not contracts:
        return "Keine unterzeichneten AVV verknuepft."
    return _format_avv(contracts)


def _format_avv(contracts: list[AVVContractModel]) -> str:
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
    case_id: UUID,
    payload: dict[str, Any],
    created_by: str = "",
) -> "PrivacyPolicyModel":
    """Persistiert eine generierte Datenschutzerklaerung und vergibt eine
    fortlaufende Versionsnummer pro Case."""
    next_version_result = await db.execute(
        select(func.coalesce(func.max(PrivacyPolicyModel.version), 0)).where(
            PrivacyPolicyModel.case_id == case_id
        )
    )
    next_version = int(next_version_result.scalar_one() or 0) + 1

    model = PrivacyPolicyModel(
        case_id=case_id,
        version=next_version,
        title=payload.get("title", "Datenschutzerklärung"),
        content_markdown=payload.get("content_markdown", ""),
        version_note=payload.get("version_note", ""),
        payload=payload,
        generated_at=datetime.now(UTC),
        created_by=created_by,
    )
    db.add(model)
    await db.flush()
    await db.refresh(model)
    return model


async def list_privacy_policies_for_case(
    db: AsyncSession, case_id: UUID
) -> list["PrivacyPolicyModel"]:
    """Gibt alle Versionen fuer einen Case zurueck (neueste zuerst)."""
    result = await db.execute(
        select(PrivacyPolicyModel)
        .where(PrivacyPolicyModel.case_id == case_id)
        .order_by(PrivacyPolicyModel.version.desc())
    )
    return list(result.scalars().all())


async def list_privacy_policies(db: AsyncSession) -> list["PrivacyPolicyModel"]:
    """Gibt alle gespeicherten Datenschutzerklaerungen zurueck (neueste zuerst).

    Wird fuer die globale read-only Uebersicht verwendet.
    """
    result = await db.execute(
        select(PrivacyPolicyModel).order_by(PrivacyPolicyModel.generated_at.desc())
    )
    return list(result.scalars().all())
