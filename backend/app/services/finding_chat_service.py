"""LLM-gestützter Befund-Chat-Assistent: kontextbewusstes Q&A pro Befund."""

import logging
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.llm import create_agent, llm_retry_call
from app.core.prompt_security import sanitize_prompt_field
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
    evidence_text = (
        "\n".join(f"- {e}" for e in (finding.evidence or []))
        or "Keine Nachweise vorhanden."
    )
    doc_context = ""
    if document and document.content:
        excerpt = document.content[:_MAX_DOC_CHARS]
        if len(document.content) > _MAX_DOC_CHARS:
            excerpt += "\n[... Dokument gekürzt ...]"
        doc_context = f"**Relevanter Dokumentauszug ({document.name})**:\n{sanitize_prompt_field(excerpt, max_chars=_MAX_DOC_CHARS)}"

    return _CHAT_SYSTEM_TEMPLATE.format(
        check_name=sanitize_prompt_field(finding.check_name, max_chars=200),
        category=sanitize_prompt_field(finding.category, max_chars=100),
        severity=sanitize_prompt_field(finding.severity, max_chars=50),
        description=sanitize_prompt_field(finding.description, max_chars=1000),
        recommendation=sanitize_prompt_field(
            finding.recommendation or "Keine Empfehlung vorhanden.", max_chars=500
        ),
        evidence=sanitize_prompt_field(evidence_text, max_chars=1000),
        doc_context=doc_context,
    )


async def chat_with_finding(
    finding_id: UUID,
    user_message: str,
    db: AsyncSession,
) -> str:
    """Sendet eine Nutzernachricht an den LLM im Kontext des Befundes und gibt die Antwort zurück."""
    finding_result = await db.execute(
        select(FindingModel).where(FindingModel.id == finding_id)
    )
    finding = finding_result.scalar_one_or_none()
    if not finding:
        raise ValueError(f"Finding {finding_id} not found")

    logger.info(
        "Finding chat request",
        extra={"finding_id": str(finding_id), "case_id": str(finding.case_id)},
    )

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
    result = await llm_retry_call(agent, full_user_content, output_type=str)
    response_text = result.output
    logger.debug(
        "Finding chat response generated",
        extra={"finding_id": str(finding_id), "response_length": len(response_text)},
    )

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
