"""DSR-Service: Antwortschreiben für Betroffenenrechts-Anfragen (Art. 15–22 DSGVO) per LLM generieren."""
import logging
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.llm import create_agent
from app.models.db import DSRActivityLogModel, DSRRequestModel

logger = logging.getLogger(__name__)

_REQUEST_TYPE_LABELS = {
    "access": "Auskunftsrecht (Art. 15 DSGVO)",
    "rectification": "Recht auf Berichtigung (Art. 16 DSGVO)",
    "erasure": "Recht auf Löschung (Art. 17 DSGVO)",
    "portability": "Recht auf Datenübertragbarkeit (Art. 20 DSGVO)",
    "restriction": "Recht auf Einschränkung der Verarbeitung (Art. 18 DSGVO)",
    "objection": "Widerspruchsrecht (Art. 21 DSGVO)",
}

_SYSTEM_PROMPT = """Du bist ein Datenschutzbeauftragter und erstellst professionelle Antwortschreiben auf Betroffenenrechts-Anfragen gemäß DSGVO.

Erstelle ein formelles, rechtlich korrektes Antwortschreiben das:
- Die zutreffenden DSGVO-Artikel korrekt zitiert
- Die Rechte der betroffenen Person anerkennt
- Die nächsten Schritte klar beschreibt
- Einen professionellen Briefkopf-Platzhalter enthält
- Auf Deutsch verfasst ist

Halte den Ton professionell und respektvoll."""

_USER_TEMPLATE = """Erstelle ein Antwortschreiben für folgende Betroffenenrechts-Anfrage:

**Art der Anfrage**: {request_type_label}
**Abteilung**: {department}
**Beschreibung der Anfrage**: {description}
**Eingangsdatum**: {received_at}
**Antwortfrist**: {response_deadline}

Das Schreiben soll:
1. Die Anfrage bestätigen
2. Die zutreffenden Rechtsgrundlagen nennen
3. Die vorgesehene Vorgehensweise erläutern
4. Eine Bearbeitungszeit von max. {days_remaining} Tagen bis zur vollständigen Antwort ankündigen

Beginne mit "[BRIEFKOPF ORGANISATION]" und "[DATUM]" als Platzhalter."""


async def generate_draft_response(request_id: UUID, db: AsyncSession) -> str:
    """Generiert einen LLM-Entwurf für das Antwortschreiben einer DSR-Anfrage."""
    from datetime import date
    result = await db.execute(select(DSRRequestModel).where(DSRRequestModel.id == request_id))
    request = result.scalar_one_or_none()
    if not request:
        raise ValueError(f"DSR request {request_id} not found")

    today = date.today()
    days_remaining = max(0, (request.response_deadline - today).days)
    request_type_label = _REQUEST_TYPE_LABELS.get(request.request_type, request.request_type)

    logger.info(
        "Generating DSR draft response",
        extra={"dsr_request_id": str(request_id), "request_type": request.request_type, "days_remaining": days_remaining},
    )

    user_content = _USER_TEMPLATE.format(
        request_type_label=request_type_label,
        department=request.department or "Nicht angegeben",
        description=request.description or "Keine Beschreibung vorhanden.",
        received_at=request.received_at.strftime("%d.%m.%Y"),
        response_deadline=request.response_deadline.strftime("%d.%m.%Y"),
        days_remaining=days_remaining,
    )

    agent = create_agent(_SYSTEM_PROMPT)
    result_llm = await agent.run(user_content)
    draft = str(result_llm.data)
    logger.info(
        "DSR draft response generated",
        extra={"dsr_request_id": str(request_id), "draft_length": len(draft)},
    )

    # Draft speichern
    request.draft_response = draft

    activity = DSRActivityLogModel(
        request_id=request_id,
        event_type="draft_generated",
        payload={"days_remaining": days_remaining},
    )
    db.add(activity)
    await db.flush()

    return draft
