"""E-Mail-Benachrichtigungen für Fristen und überfällige Befunde."""
import logging
import smtplib
import ssl
from datetime import date, datetime, timedelta, timezone
from email.message import EmailMessage

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.constants import CaseStatus
from app.models.db import (
    ActivityLogModel,
    AVVContractModel,
    CaseModel,
    DataBreachActivityLogModel,
    DataBreachModel,
    DSRActivityLogModel,
    DSRRequestModel,
    UserModel,
)

# Mindestabstand zwischen zwei Benachrichtigungen derselben Entität (Anti-Spam).
# Verhindert tägliche E-Mail-Flut bei langen Warnfenstern.
_NOTIFICATION_COOLDOWN_HOURS = 20

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
                smtp.login(settings.smtp_username, settings.smtp_password.get_secret_value())
            smtp.send_message(msg)
    else:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as smtp:
            if settings.smtp_username:
                smtp.login(settings.smtp_username, settings.smtp_password.get_secret_value())
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
                    smtp.login(settings.smtp_username, settings.smtp_password.get_secret_value())
        else:
            with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=5) as smtp:
                if settings.smtp_username:
                    smtp.login(settings.smtp_username, settings.smtp_password.get_secret_value())
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
    now_utc = datetime.now(timezone.utc)
    cooldown = timedelta(hours=_NOTIFICATION_COOLDOWN_HOURS)

    # Vorgänge mit bevorstehender Frist
    cases_result = await db.execute(
        select(CaseModel).where(
            and_(
                CaseModel.archived_at == None,  # noqa: E711
                CaseModel.status != CaseStatus.COMPLETED,
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
            logger.info(
                "deadline_warning skipped: assignee '%s' for case %s has no registered user with e-mail",
                case.assignee, case.id,
            )
            continue
        # Anti-Spam: nicht öfter als einmal pro Cooldown-Fenster benachrichtigen
        if case.last_notified_at and (now_utc - case.last_notified_at) < cooldown:
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
            case.last_notified_at = now_utc
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
                CaseModel.status != CaseStatus.COMPLETED,
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
            logger.info(
                "deadline_overdue skipped: assignee '%s' for case %s has no registered user with e-mail",
                case.assignee, case.id,
            )
            continue
        # Anti-Spam: nicht öfter als einmal pro Cooldown-Fenster benachrichtigen
        if case.last_notified_at and (now_utc - case.last_notified_at) < cooldown:
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
            case.last_notified_at = now_utc
            activity = ActivityLogModel(
                case_id=case.id,
                event_type="notification_sent",
                payload={"type": "deadline_overdue", "recipient": assignee_user.email, "days_overdue": days_overdue},
            )
            db.add(activity)
            sent_count += 1
        except Exception as exc:
            logger.warning("Failed to send overdue notification for case %s: %s", case.id, exc)

    # -------------------------------------------------------
    # Datenpannen: 72-Stunden-Meldepflicht (Art. 33 DSGVO)
    # -------------------------------------------------------
    now = now_utc  # Alias für Datenpannen-Abschnitt (timezone-aware)
    breach_warning_dt = now + timedelta(hours=settings.notification_breach_warning_hours)

    breaches_result = await db.execute(
        select(DataBreachModel).where(
            and_(
                DataBreachModel.status.in_(["discovered", "assessed"]),
                DataBreachModel.notification_deadline != None,  # noqa: E711
                DataBreachModel.notification_deadline <= breach_warning_dt,
                DataBreachModel.notification_deadline >= now,
            )
        )
    )
    for breach in breaches_result.scalars().all():
        if not breach.assignee:
            continue
        assignee_user = users_by_name.get(breach.assignee.lower())
        if not assignee_user or not assignee_user.email:
            logger.info(
                "breach_warning skipped: assignee '%s' for breach %s has no registered user with e-mail",
                breach.assignee, breach.id,
            )
            continue
        # Anti-Spam: nicht öfter als einmal pro Cooldown-Fenster benachrichtigen
        if breach.last_notified_at and (now - breach.last_notified_at) < cooldown:
            continue
        hours_left = max(0, int((breach.notification_deadline - now).total_seconds() / 3600))
        subject = f"[Datenschutzagent] Datenpanne – Meldepflicht in {hours_left}h: {breach.title}"
        body = (
            f"Guten Tag {assignee_user.display_name},\n\n"
            f"die 72-Stunden-Meldepflicht (Art. 33 DSGVO) für folgende Datenpanne läuft ab:\n\n"
            f"  Titel: {breach.title}\n"
            f"  Meldepflicht bis: {breach.notification_deadline.strftime('%d.%m.%Y %H:%M')} UTC\n"
            f"  Verbleibende Zeit: ca. {hours_left} Stunde(n)\n\n"
            f"Bitte prüfen Sie den Meldestand umgehend.\n\n"
            f"-- Datenschutzagent"
        )
        try:
            _send_email(assignee_user.email, subject, body)
            breach.last_notified_at = now
            db.add(DataBreachActivityLogModel(
                breach_id=breach.id,
                event_type="notification_sent",
                payload={"type": "breach_warning", "recipient": assignee_user.email, "hours_left": hours_left},
            ))
            sent_count += 1
        except Exception as exc:
            logger.warning("Failed to send breach notification for breach %s: %s", breach.id, exc)

    # Überfällige Datenpannen (Meldepflicht abgelaufen, noch nicht abgeschlossen)
    overdue_breaches_result = await db.execute(
        select(DataBreachModel).where(
            and_(
                DataBreachModel.status.in_(["discovered", "assessed"]),
                DataBreachModel.notification_deadline < now,
            )
        )
    )
    for breach in overdue_breaches_result.scalars().all():
        if not breach.assignee:
            continue
        assignee_user = users_by_name.get(breach.assignee.lower())
        if not assignee_user or not assignee_user.email:
            logger.info(
                "breach_overdue skipped: assignee '%s' for breach %s has no registered user with e-mail",
                breach.assignee, breach.id,
            )
            continue
        # Anti-Spam: nicht öfter als einmal pro Cooldown-Fenster benachrichtigen
        if breach.last_notified_at and (now - breach.last_notified_at) < cooldown:
            continue
        hours_overdue = max(0, int((now - breach.notification_deadline).total_seconds() / 3600))
        subject = f"[Datenschutzagent] ÜBERFÄLLIG – Datenpanne nicht gemeldet ({hours_overdue}h): {breach.title}"
        body = (
            f"Guten Tag {assignee_user.display_name},\n\n"
            f"die 72-Stunden-Meldepflicht für folgende Datenpanne ist ÜBERSCHRITTEN:\n\n"
            f"  Titel: {breach.title}\n"
            f"  Meldepflicht war: {breach.notification_deadline.strftime('%d.%m.%Y %H:%M')} UTC\n"
            f"  Überfällig seit: ca. {hours_overdue} Stunde(n)\n\n"
            f"Bitte handeln Sie sofort und dokumentieren Sie den Vorgang.\n\n"
            f"-- Datenschutzagent"
        )
        try:
            _send_email(assignee_user.email, subject, body)
            breach.last_notified_at = now
            db.add(DataBreachActivityLogModel(
                breach_id=breach.id,
                event_type="notification_sent",
                payload={"type": "breach_overdue", "recipient": assignee_user.email, "hours_overdue": hours_overdue},
            ))
            sent_count += 1
        except Exception as exc:
            logger.warning("Failed to send overdue breach notification for breach %s: %s", breach.id, exc)

    # -------------------------------------------------------
    # DSR-Anfragen: 30-Tage-Antwortpflicht (Art. 12 DSGVO)
    # -------------------------------------------------------
    dsr_warning_date = today + timedelta(days=settings.notification_dsr_warning_days)

    dsr_result = await db.execute(
        select(DSRRequestModel).where(
            and_(
                DSRRequestModel.status.in_(["received", "in_progress"]),
                DSRRequestModel.response_deadline != None,  # noqa: E711
                DSRRequestModel.response_deadline <= dsr_warning_date,
                DSRRequestModel.response_deadline >= today,
            )
        )
    )
    for dsr in dsr_result.scalars().all():
        if not dsr.assignee:
            continue
        assignee_user = users_by_name.get(dsr.assignee.lower())
        if not assignee_user or not assignee_user.email:
            logger.info(
                "dsr_warning skipped: assignee '%s' for DSR %s has no registered user with e-mail",
                dsr.assignee, dsr.id,
            )
            continue
        # Anti-Spam: nicht öfter als einmal pro Cooldown-Fenster benachrichtigen
        dsr_last = dsr.last_notified_at
        if dsr_last and dsr_last.tzinfo is None:
            dsr_last = dsr_last.replace(tzinfo=timezone.utc)
        if dsr_last and (now_utc - dsr_last) < cooldown:
            continue
        days_left = (dsr.response_deadline - today).days
        req_type_labels = {
            "access": "Auskunft", "rectification": "Berichtigung",
            "erasure": "Löschung", "portability": "Datenübertragbarkeit",
            "restriction": "Einschränkung", "objection": "Widerspruch",
        }
        req_label = req_type_labels.get(dsr.request_type, dsr.request_type)
        subject = f"[Datenschutzagent] DSR-Anfrage ({req_label}) – Antwortfrist in {days_left} Tag(en)"
        body = (
            f"Guten Tag {assignee_user.display_name},\n\n"
            f"folgende Betroffenenrechts-Anfrage (Art. 12 DSGVO) muss beantwortet werden:\n\n"
            f"  Anfrageart: {req_label}\n"
            f"  Antragsteller: {dsr.requestor_name or '(unbekannt)'}\n"
            f"  Antwortpflicht bis: {dsr.response_deadline.strftime('%d.%m.%Y')} (in {days_left} Tag(en))\n\n"
            f"Bitte bearbeiten Sie die Anfrage zeitnah.\n\n"
            f"-- Datenschutzagent"
        )
        try:
            _send_email(assignee_user.email, subject, body)
            dsr.last_notified_at = now_utc
            db.add(DSRActivityLogModel(
                request_id=dsr.id,
                event_type="notification_sent",
                payload={"type": "dsr_warning", "recipient": assignee_user.email, "days_left": days_left},
            ))
            sent_count += 1
        except Exception as exc:
            logger.warning("Failed to send DSR notification for DSR %s: %s", dsr.id, exc)

    # -------------------------------------------------------
    # AVV-Verträge: Ablaufwarnung
    # -------------------------------------------------------
    avv_warning_date = today + timedelta(days=settings.notification_avv_expiry_warning_days)

    avv_result = await db.execute(
        select(AVVContractModel).where(
            and_(
                AVVContractModel.status == "signed",
                AVVContractModel.expiry_date != None,  # noqa: E711
                AVVContractModel.expiry_date <= avv_warning_date,
                AVVContractModel.expiry_date >= today,
            )
        )
    )
    for avv in avv_result.scalars().all():
        if not avv.assignee:
            continue
        assignee_user = users_by_name.get(avv.assignee.lower())
        if not assignee_user or not assignee_user.email:
            logger.info(
                "avv_expiry skipped: assignee '%s' for AVV %s has no registered user with e-mail",
                avv.assignee, avv.id,
            )
            continue
        # Anti-Spam: nicht öfter als einmal pro Cooldown-Fenster benachrichtigen
        if avv.last_notified_at and (now_utc - avv.last_notified_at) < cooldown:
            continue
        days_left = (avv.expiry_date - today).days
        subject = f"[Datenschutzagent] AVV läuft ab in {days_left} Tag(en): {avv.partner_name}"
        body = (
            f"Guten Tag {assignee_user.display_name},\n\n"
            f"folgender Auftragsverarbeitungsvertrag (Art. 28 DSGVO) läuft demnächst ab:\n\n"
            f"  Partner: {avv.partner_name}\n"
            f"  Vertragsart: {'Auftragsverarbeiter' if avv.partner_type == 'processor' else 'Unter-AV'}\n"
            f"  Ablaufdatum: {avv.expiry_date.strftime('%d.%m.%Y')} (in {days_left} Tag(en))\n\n"
            f"Bitte erneuern oder kündigen Sie den Vertrag rechtzeitig.\n\n"
            f"-- Datenschutzagent"
        )
        try:
            _send_email(assignee_user.email, subject, body)
            avv.last_notified_at = now_utc
            sent_count += 1
        except Exception as exc:
            logger.warning("Failed to send AVV expiry notification for AVV %s: %s", avv.id, exc)

    if sent_count > 0:
        await db.flush()

    logger.info("Deadline notification scan complete", extra={"sent": sent_count})
    return {"sent": sent_count}
