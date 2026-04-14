"""Service für Datenpannen-Management: LLM-gestützte Behörden-Meldungsgenerierung."""
import logging
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db import DataBreachModel, DataBreachActivityLogModel

logger = logging.getLogger(__name__)


_NOTIFICATION_PROMPT = """Du bist ein Datenschutzbeauftragter und erstellst eine Meldung an die Datenschutz-Aufsichtsbehörde gemäß Art. 33 DSGVO.

Erstelle einen strukturierten Meldungsentwurf auf Deutsch mit folgenden Abschnitten:
1. Beschreibung der Verletzung (Art, Umstände, Zeitpunkt)
2. Kategorien und ungefähre Anzahl der betroffenen Personen und Datensätze
3. Wahrscheinliche Folgen der Verletzung
4. Ergriffene oder geplante Maßnahmen zur Behebung

Datenpanne-Details:
Titel: {title}
Beschreibung: {description}
Entdeckt am: {discovered_at}
Art der Verletzung: {breach_type}
Betroffene Datenkategorien: {categories}
Betroffene Personen: {persons_count}
Abteilung: {department}
Risikostufe: {risk_level}
Bereits ergriffene Maßnahmen: {measures}

Erstelle einen formalen Meldungsentwurf, der alle Pflichtangaben nach Art. 33 Abs. 3 DSGVO enthält.
"""

_BREACH_TYPE_LABELS = {
    "confidentiality": "Vertraulichkeitsverletzung",
    "integrity": "Integritätsverletzung",
    "availability": "Verfügbarkeitsverletzung",
}


async def generate_breach_notification(breach_id: UUID, db: AsyncSession) -> None:
    """Generiert per LLM einen Behörden-Meldungsentwurf und speichert ihn in der DB."""
    result = await db.execute(select(DataBreachModel).where(DataBreachModel.id == breach_id))
    breach = result.scalar_one_or_none()
    if not breach:
        logger.warning("Data breach not found", extra={"breach_id": str(breach_id)})
        return

    logger.info("Generating breach notification draft", extra={"breach_id": str(breach_id)})

    try:
        from app.config import settings
        if not settings.ollama_enabled:
            breach.draft_notification = _build_template_notification(breach)
            logger.info("Breach notification generated via template (LLM disabled)", extra={"breach_id": str(breach_id)})
            activity = DataBreachActivityLogModel(
                breach_id=breach_id,
                event_type="notification_draft_generated",
                payload={"method": "template"},
            )
            db.add(activity)
            await db.flush()
            return

        prompt = _NOTIFICATION_PROMPT.format(
            title=breach.title,
            description=breach.description or "Keine Beschreibung",
            discovered_at=breach.discovered_at.strftime("%d.%m.%Y %H:%M UTC"),
            breach_type=_BREACH_TYPE_LABELS.get(breach.breach_type, breach.breach_type),
            categories=", ".join(breach.affected_data_categories or []) or "Nicht angegeben",
            persons_count=str(breach.affected_persons_count) if breach.affected_persons_count else "Unbekannt",
            department=breach.department or "Nicht angegeben",
            risk_level=breach.risk_level or "Nicht bewertet",
            measures=breach.measures_taken or "Keine",
        )

        import httpx
        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(
                f"{settings.ollama_base_url}/api/generate",
                json={
                    "model": settings.ollama_model,
                    "prompt": prompt,
                    "stream": False,
                },
            )
            response.raise_for_status()
            data = response.json()
            draft = data.get("response", "").strip()

        breach.draft_notification = draft if draft else _build_template_notification(breach)
        method = "llm" if draft else "template_fallback"
        logger.info(
            "Breach notification generated via LLM",
            extra={"breach_id": str(breach_id), "method": method, "draft_length": len(breach.draft_notification)},
        )

    except Exception as exc:
        logger.warning(
            "LLM breach notification failed, using template fallback: %s", exc,
            extra={"breach_id": str(breach_id)},
        )
        breach.draft_notification = _build_template_notification(breach)

    activity = DataBreachActivityLogModel(
        breach_id=breach_id,
        event_type="notification_draft_generated",
        payload={"method": "llm"},
    )
    db.add(activity)
    await db.flush()


def _build_template_notification(breach: DataBreachModel) -> str:
    """Erstellt einen Basis-Meldungsentwurf ohne LLM als Fallback."""
    breach_label = _BREACH_TYPE_LABELS.get(breach.breach_type, breach.breach_type)
    categories = ", ".join(breach.affected_data_categories or []) or "Nicht angegeben"
    persons = str(breach.affected_persons_count) if breach.affected_persons_count else "Unbekannt"

    return f"""# Meldung einer Datenschutzverletzung gemäß Art. 33 DSGVO

**Verantwortlicher:** [Bitte ergänzen]
**Datenschutzbeauftragter:** [Bitte ergänzen]
**Meldedatum:** {breach.discovered_at.strftime('%d.%m.%Y')}

## 1. Beschreibung der Verletzung

**Titel:** {breach.title}
**Art der Verletzung:** {breach_label}
**Zeitpunkt der Entdeckung:** {breach.discovered_at.strftime('%d.%m.%Y %H:%M UTC')}
**Betroffene Abteilung:** {breach.department or 'Nicht angegeben'}

{breach.description or '[Bitte Beschreibung ergänzen]'}

## 2. Betroffene Personen und Datenkategorien

**Kategorien betroffener Daten:** {categories}
**Ungefähre Anzahl betroffener Personen:** {persons}
**Ungefähre Anzahl betroffener Datensätze:** [Bitte ergänzen]

## 3. Wahrscheinliche Folgen

[Bitte wahrscheinliche Folgen der Verletzung beschreiben]

## 4. Ergriffene und geplante Maßnahmen

{breach.measures_taken or '[Bitte ergriffene Maßnahmen beschreiben]'}

---
*Dieser Entwurf muss vor dem Versand geprüft und vervollständigt werden.*
*Gesetzliche Meldefrist: 72 Stunden nach Entdeckung (Art. 33 Abs. 1 DSGVO)*
"""
