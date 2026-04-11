"""LLM-gestützter Befund-Chat-Assistent: kontextbewusstes Q&A pro Befund."""
import logging
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.llm import create_agent
from app.models.db import DocumentModel, FindingChatMessageModel, FindingModel

logger = logging.getLogger(__name__)

_CHAT_SYSTEM_TEMPLATE = """Du bist ein DSGVO-Compliance-Experte. Du hilfst bei der Analyse und Behebung eines konkreten Datenschutz-Befundes.

**Befund**: {check_name}
**Kategorie**: {category}
**Schweregrad**: {severity}
**Beschreibung**: {description}
**Empfehlung**: {recommendation}
**Nachweise**:
{evidence}

{doc_context}

Beantworte Fragen zu diesem Befund präzise und praxisnah. Schlage konkrete Verbesserungen vor.
Antworte auf Deutsch, es sei denn, der Nutzer fragt auf Englisch."""

_MAX_DOC_CHARS = 3000


def _build_system_prompt(finding: FindingModel, document: DocumentModel | None) -> str:
    evidence_text = "\n".join(f"- {e}" for e in (finding.evidence or [])) or "Keine Nachweise vorhanden."
    doc_context = ""
    if document and document.content:
        excerpt = document.content[:_MAX_DOC_CHARS]
        if len(document.content) > _MAX_DOC_CHARS:
            excerpt += "\n[... Dokument gekürzt ...]"
        doc_context = f"**Relevanter Dokumentauszug ({document.name})**:\n{excerpt}"

    return _CHAT_SYSTEM_TEMPLATE.format(
        check_name=finding.check_name,
        category=finding.category,
        severity=finding.severity,
        description=finding.description,
        recommendation=finding.recommendation or "Keine Empfehlung vorhanden.",
        evidence=evidence_text,
        doc_context=doc_context,
    )


async def chat_with_finding(
    finding_id: UUID,
    user_message: str,
    db: AsyncSession,
) -> str:
    """Sendet eine Nutzernachricht an den LLM im Kontext des Befundes und gibt die Antwort zurück."""
    finding_result = await db.execute(select(FindingModel).where(FindingModel.id == finding_id))
    finding = finding_result.scalar_one_or_none()
    if not finding:
        raise ValueError(f"Finding {finding_id} not found")

    document: DocumentModel | None = None
    if finding.document_id:
        doc_result = await db.execute(
            select(DocumentModel).where(DocumentModel.id == finding.document_id)
        )
        document = doc_result.scalar_one_or_none()

    # Vorherige Chat-Nachrichten laden (max. 10 für Kontext)
    history_result = await db.execute(
        select(FindingChatMessageModel)
        .where(FindingChatMessageModel.finding_id == finding_id)
        .order_by(FindingChatMessageModel.created_at.desc())
        .limit(10)
    )
    history = list(reversed(history_result.scalars().all()))

    system_prompt = _build_system_prompt(finding, document)

    # Baue den User-Content mit Gesprächsverlauf auf
    conversation_parts = []
    for msg in history:
        role_label = "Nutzer" if msg.role == "user" else "Assistent"
        conversation_parts.append(f"{role_label}: {msg.content}")
    conversation_parts.append(f"Nutzer: {user_message}")
    full_user_content = "\n\n".join(conversation_parts)

    agent = create_agent(system_prompt)
    result = await agent.run(full_user_content)
    response_text = str(result.data)

    # Nachrichten persistieren
    user_msg = FindingChatMessageModel(
        finding_id=finding_id,
        case_id=finding.case_id,
        role="user",
        content=user_message,
    )
    assistant_msg = FindingChatMessageModel(
        finding_id=finding_id,
        case_id=finding.case_id,
        role="assistant",
        content=response_text,
    )
    db.add(user_msg)
    db.add(assistant_msg)
    await db.flush()

    return response_text
