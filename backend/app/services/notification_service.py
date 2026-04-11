"""E-Mail-Benachrichtigungen für Fristen und überfällige Befunde."""
import logging
import smtplib
import ssl
from datetime import date, timedelta
from email.message import EmailMessage

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.db import ActivityLogModel, CaseModel, FindingModel, UserModel

logger = logging.getLogger(__name__)


def _send_email(to_address: str, subject: str, body: str) -> None:
    """Sendet eine E-Mail via SMTP. Raises on failure."""
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = settings.smtp_from_address
    msg["To"] = to_address
    msg.set_content(body)

    if settings.smtp_tls:
        context = ssl.create_default_context()
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as smtp:
            smtp.ehlo()
            smtp.starttls(context=context)
            if settings.smtp_username:
                smtp.login(settings.smtp_username, settings.smtp_password)
            smtp.send_message(msg)
    else:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as smtp:
            if settings.smtp_username:
                smtp.login(settings.smtp_username, settings.smtp_password)
            smtp.send_message(msg)


def test_smtp_connection() -> dict:
    """Testet die SMTP-Verbindung. Gibt status='ok' oder 'error' zurück."""
    if not settings.smtp_enabled:
        return {"status": "disabled", "detail": "SMTP ist nicht aktiviert (SMTP_ENABLED=false)"}
    try:
        if settings.smtp_tls:
            context = ssl.create_default_context()
            with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=5) as smtp:
                smtp.ehlo()
                smtp.starttls(context=context)
                if settings.smtp_username:
                    smtp.login(settings.smtp_username, settings.smtp_password)
        else:
            with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=5) as smtp:
                if settings.smtp_username:
                    smtp.login(settings.smtp_username, settings.smtp_password)
        return {"status": "ok", "detail": f"Verbunden mit {settings.smtp_host}:{settings.smtp_port}"}
    except Exception as exc:
        return {"status": "error", "detail": str(exc)}


async def scan_and_notify_deadlines(db: AsyncSession) -> dict:
    """Scannt Vorgänge und Befunde auf bevorstehende/überschrittene Fristen und sendet E-Mails.

    Returns summary dict with counts.
    """
    if not settings.smtp_enabled:
        logger.info("Deadline notifications skipped: SMTP not enabled")
        return {"sent": 0, "skipped_no_smtp": True}

    today = date.today()
    warning_date = today + timedelta(days=settings.notification_deadline_warning_days)

    # Alle aktiven Nutzer mit E-Mail laden
    users_result = await db.execute(
        select(UserModel).where(UserModel.email != None)  # noqa: E711
    )
    users_by_name: dict[str, UserModel] = {}
    for u in users_result.scalars().all():
        if u.email:
            users_by_name[u.display_name.lower()] = u

    sent_count = 0

    # Vorgänge mit bevorstehender Frist
    cases_result = await db.execute(
        select(CaseModel).where(
            and_(
                CaseModel.archived_at == None,  # noqa: E711
                CaseModel.status != "completed",
                CaseModel.deadline != None,  # noqa: E711
                CaseModel.deadline <= warning_date,
                CaseModel.deadline >= today,
            )
        )
    )
    for case in cases_result.scalars().all():
        if not case.assignee:
            continue
        assignee_user = users_by_name.get(case.assignee.lower())
        if not assignee_user or not assignee_user.email:
            continue
        days_left = (case.deadline - today).days
        subject = f"[Datenschutzagent] Frist in {days_left} Tag(en): {case.title}"
        body = (
            f"Guten Tag {assignee_user.display_name},\n\n"
            f"der Vorgang '{case.title}' (Abteilung: {case.department}) hat eine bevorstehende Frist:\n"
            f"  Fällig am: {case.deadline.strftime('%d.%m.%Y')} (in {days_left} Tag(en))\n\n"
            f"Bitte prüfen Sie den aktuellen Status.\n\n"
            f"-- Datenschutzagent"
        )
        try:
            _send_email(assignee_user.email, subject, body)
            activity = ActivityLogModel(
                case_id=case.id,
                event_type="notification_sent",
                payload={"type": "deadline_warning", "recipient": assignee_user.email, "days_left": days_left},
            )
            db.add(activity)
            sent_count += 1
        except Exception as exc:
            logger.warning("Failed to send deadline notification for case %s: %s", case.id, exc)

    # Vorgänge mit überschrittener Frist
    overdue_result = await db.execute(
        select(CaseModel).where(
            and_(
                CaseModel.archived_at == None,  # noqa: E711
                CaseModel.status != "completed",
                CaseModel.deadline != None,  # noqa: E711
                CaseModel.deadline < today,
            )
        )
    )
    for case in overdue_result.scalars().all():
        if not case.assignee:
            continue
        assignee_user = users_by_name.get(case.assignee.lower())
        if not assignee_user or not assignee_user.email:
            continue
        days_overdue = (today - case.deadline).days
        subject = f"[Datenschutzagent] ÜBERFÄLLIG ({days_overdue}d): {case.title}"
        body = (
            f"Guten Tag {assignee_user.display_name},\n\n"
            f"der Vorgang '{case.title}' ist seit {days_overdue} Tag(en) überfällig:\n"
            f"  Frist war: {case.deadline.strftime('%d.%m.%Y')}\n\n"
            f"Bitte bearbeiten Sie diesen Vorgang umgehend.\n\n"
            f"-- Datenschutzagent"
        )
        try:
            _send_email(assignee_user.email, subject, body)
            activity = ActivityLogModel(
                case_id=case.id,
                event_type="notification_sent",
                payload={"type": "deadline_overdue", "recipient": assignee_user.email, "days_overdue": days_overdue},
            )
            db.add(activity)
            sent_count += 1
        except Exception as exc:
            logger.warning("Failed to send overdue notification for case %s: %s", case.id, exc)

    if sent_count > 0:
        await db.flush()

    logger.info("Deadline notification scan complete", extra={"sent": sent_count})
    return {"sent": sent_count}
