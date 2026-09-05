"""E-Mail-Benachrichtigungen für Fristen und überfällige Befunde."""

import asyncio
import logging
import smtplib
import ssl
from collections.abc import Callable, Sequence
from datetime import UTC, date, datetime, timedelta
from email.message import EmailMessage
from typing import Any

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.constants import CaseStatus, FindingSeverity, FindingStatus
from app.models.db import (
    ActivityLogModel,
    AVVContractModel,
    CaseModel,
    DataBreachActivityLogModel,
    DataBreachModel,
    DSRActivityLogModel,
    DSRRequestModel,
    FindingModel,
    UserModel,
)

# Mindestabstand zwischen zwei Benachrichtigungen derselben Entität (Anti-Spam).
# Verhindert tägliche E-Mail-Flut bei langen Warnfenstern.
_NOTIFICATION_COOLDOWN_HOURS = 20

logger = logging.getLogger(__name__)


def _user_accepts_notifications(user: UserModel | None) -> bool:
    """Master-Switch je Nutzer (Item 15). Default true wenn das Attribut fehlt
    (Backward-Compat für Tests mit alten Fixtures)."""
    if user is None or not user.email:
        return False
    return bool(getattr(user, "notifications_enabled", True))


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
                smtp.login(
                    settings.smtp_username, settings.smtp_password.get_secret_value()
                )
            smtp.send_message(msg)
    else:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as smtp:
            if settings.smtp_username:
                smtp.login(
                    settings.smtp_username, settings.smtp_password.get_secret_value()
                )
            smtp.send_message(msg)


async def _send_email_async(to_address: str, subject: str, body: str) -> None:
    """``_send_email`` in a worker thread: smtplib blocks for seconds per mail and the
    scans run inside FastAPI's event loop (admin trigger) as well as in Celery."""
    await asyncio.to_thread(_send_email, to_address, subject, body)


def test_smtp_connection() -> dict:
    """Testet die SMTP-Verbindung. Gibt status='ok' oder 'error' zurück."""
    if not settings.smtp_enabled:
        return {
            "status": "disabled",
            "detail": "SMTP ist nicht aktiviert (SMTP_ENABLED=false)",
        }
    try:
        if settings.smtp_tls:
            context = ssl.create_default_context()
            with smtplib.SMTP(
                settings.smtp_host, settings.smtp_port, timeout=5
            ) as smtp:
                smtp.ehlo()
                smtp.starttls(context=context)
                if settings.smtp_username:
                    smtp.login(
                        settings.smtp_username,
                        settings.smtp_password.get_secret_value(),
                    )
        else:
            with smtplib.SMTP(
                settings.smtp_host, settings.smtp_port, timeout=5
            ) as smtp:
                if settings.smtp_username:
                    smtp.login(
                        settings.smtp_username,
                        settings.smtp_password.get_secret_value(),
                    )
        return {
            "status": "ok",
            "detail": f"Verbunden mit {settings.smtp_host}:{settings.smtp_port}",
        }
    except Exception as exc:  # noqa: BLE001 – health check reports any failure
        return {"status": "error", "detail": str(exc)}


# ---------------------------------------------------------------------------
# Generic per-entity notification loop (Qualitätsplan Phase 2 R7)
# ---------------------------------------------------------------------------
#
# Every deadline scan is the same five steps — assignee lookup, cooldown, message,
# send, activity/marker — applied to a different entity type. The differences are
# isolated in small message builders below; ``_notify_entities`` owns the loop.

# (subject, body, activity payload) for one entity/recipient pair
_Message = tuple[str, str, dict[str, Any]]


def _normalize_ts(value: datetime | None) -> datetime | None:
    """Naive timestamps (legacy rows) are interpreted as UTC so cooldown math works."""
    if value is not None and value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


async def _notify_entities(
    db: AsyncSession,
    entities: Sequence[Any],
    users_by_name: dict[str, UserModel],
    *,
    now_utc: datetime,
    cooldown: timedelta,
    kind: str,
    build_message: Callable[[Any, UserModel], _Message | None],
    make_activity: Callable[[Any, dict[str, Any]], Any] | None = None,
) -> int:
    """Send one e-mail per entity to its assignee; returns the number sent.

    Skips entities without assignee, without a registered recipient, or inside the
    cooldown window. A failed send is logged and never aborts the scan.
    """
    sent = 0
    for entity in entities:
        assignee = getattr(entity, "assignee", None)
        if not assignee:
            continue
        user = users_by_name.get(assignee.lower())
        if not user or not user.email:
            logger.info(
                "%s skipped: assignee '%s' for %s has no registered user with e-mail",
                kind,
                assignee,
                entity.id,
            )
            continue
        last = _normalize_ts(getattr(entity, "last_notified_at", None))
        if last and (now_utc - last) < cooldown:
            continue
        message = build_message(entity, user)
        if message is None:
            continue
        subject, body, payload = message
        try:
            await _send_email_async(user.email, subject, body)
        # One failed mail must not stop the scan.
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to send %s for %s: %s", kind, entity.id, exc)
            continue
        entity.last_notified_at = now_utc
        if make_activity is not None:
            activity = make_activity(
                entity, {"type": kind, "recipient_user_id": str(user.id), **payload}
            )
            if activity is not None:
                db.add(activity)
        sent += 1
    return sent


def _case_activity(case: CaseModel, payload: dict[str, Any]) -> ActivityLogModel:
    return ActivityLogModel(
        case_id=case.id, event_type="notification_sent", payload=payload
    )


def _breach_activity(
    breach: DataBreachModel, payload: dict[str, Any]
) -> DataBreachActivityLogModel:
    return DataBreachActivityLogModel(
        breach_id=breach.id, event_type="notification_sent", payload=payload
    )


def _dsr_activity(dsr: DSRRequestModel, payload: dict[str, Any]) -> DSRActivityLogModel:
    return DSRActivityLogModel(
        request_id=dsr.id, event_type="notification_sent", payload=payload
    )


def _msg_case_deadline(
    case: CaseModel, user: UserModel, today: date
) -> _Message | None:
    if case.deadline is None:
        return None
    days_left = (case.deadline - today).days
    subject = f"[Datenschutzagent] Frist in {days_left} Tag(en): {case.title}"
    body = (
        f"Guten Tag {user.display_name},\n\n"
        f"der Vorgang '{case.title}' (Abteilung: {case.department}) hat eine bevorstehende Frist:\n"
        f"  Fällig am: {case.deadline.strftime('%d.%m.%Y')} (in {days_left} Tag(en))\n\n"
        f"Bitte prüfen Sie den aktuellen Status.\n\n"
        f"-- Datenschutzagent"
    )
    return subject, body, {"days_left": days_left}


def _msg_case_overdue(case: CaseModel, user: UserModel, today: date) -> _Message | None:
    if case.deadline is None:
        return None
    days_overdue = (today - case.deadline).days
    subject = f"[Datenschutzagent] ÜBERFÄLLIG ({days_overdue}d): {case.title}"
    body = (
        f"Guten Tag {user.display_name},\n\n"
        f"der Vorgang '{case.title}' ist seit {days_overdue} Tag(en) überfällig:\n"
        f"  Frist war: {case.deadline.strftime('%d.%m.%Y')}\n\n"
        f"Bitte bearbeiten Sie diesen Vorgang umgehend.\n\n"
        f"-- Datenschutzagent"
    )
    return subject, body, {"days_overdue": days_overdue}


def _msg_breach_warning(
    breach: DataBreachModel, user: UserModel, now: datetime
) -> _Message | None:
    hours_left = max(
        0, int((breach.notification_deadline - now).total_seconds() / 3600)
    )
    subject = (
        f"[Datenschutzagent] Datenpanne – Meldepflicht in {hours_left}h: {breach.title}"
    )
    body = (
        f"Guten Tag {user.display_name},\n\n"
        f"die 72-Stunden-Meldepflicht (Art. 33 DSGVO) für folgende Datenpanne läuft ab:\n\n"
        f"  Titel: {breach.title}\n"
        f"  Meldepflicht bis: {breach.notification_deadline.strftime('%d.%m.%Y %H:%M')} UTC\n"
        f"  Verbleibende Zeit: ca. {hours_left} Stunde(n)\n\n"
        f"Bitte prüfen Sie den Meldestand umgehend.\n\n"
        f"-- Datenschutzagent"
    )
    return subject, body, {"hours_left": hours_left}


def _msg_breach_overdue(
    breach: DataBreachModel, user: UserModel, now: datetime
) -> _Message | None:
    hours_overdue = max(
        0, int((now - breach.notification_deadline).total_seconds() / 3600)
    )
    subject = (
        "[Datenschutzagent] ÜBERFÄLLIG – Datenpanne nicht gemeldet "
        f"({hours_overdue}h): {breach.title}"
    )
    body = (
        f"Guten Tag {user.display_name},\n\n"
        f"die 72-Stunden-Meldepflicht für folgende Datenpanne ist ÜBERSCHRITTEN:\n\n"
        f"  Titel: {breach.title}\n"
        f"  Meldepflicht war: {breach.notification_deadline.strftime('%d.%m.%Y %H:%M')} UTC\n"
        f"  Überfällig seit: ca. {hours_overdue} Stunde(n)\n\n"
        f"Bitte handeln Sie sofort und dokumentieren Sie den Vorgang.\n\n"
        f"-- Datenschutzagent"
    )
    return subject, body, {"hours_overdue": hours_overdue}


_DSR_TYPE_LABELS = {
    "access": "Auskunft",
    "rectification": "Berichtigung",
    "erasure": "Löschung",
    "portability": "Datenübertragbarkeit",
    "restriction": "Einschränkung",
    "objection": "Widerspruch",
}


def _msg_dsr_warning(
    dsr: DSRRequestModel, user: UserModel, today: date
) -> _Message | None:
    days_left = (dsr.response_deadline - today).days
    req_label = _DSR_TYPE_LABELS.get(dsr.request_type, dsr.request_type)
    subject = f"[Datenschutzagent] DSR-Anfrage ({req_label}) – Antwortfrist in {days_left} Tag(en)"
    body = (
        f"Guten Tag {user.display_name},\n\n"
        f"folgende Betroffenenrechts-Anfrage (Art. 12 DSGVO) muss beantwortet werden:\n\n"
        f"  Anfrageart: {req_label}\n"
        f"  Antragsteller: {dsr.requestor_name or '(unbekannt)'}\n"
        f"  Antwortpflicht bis: {dsr.response_deadline.strftime('%d.%m.%Y')} (in {days_left} Tag(en))\n\n"
        f"Bitte bearbeiten Sie die Anfrage zeitnah.\n\n"
        f"-- Datenschutzagent"
    )
    return subject, body, {"days_left": days_left}


def _msg_avv_expiry(
    avv: AVVContractModel, user: UserModel, today: date
) -> _Message | None:
    if avv.expiry_date is None:
        return None
    days_left = (avv.expiry_date - today).days
    partner_kind = (
        "Auftragsverarbeiter" if avv.partner_type == "processor" else "Unter-AV"
    )
    subject = (
        f"[Datenschutzagent] AVV läuft ab in {days_left} Tag(en): {avv.partner_name}"
    )
    body = (
        f"Guten Tag {user.display_name},\n\n"
        f"folgender Auftragsverarbeitungsvertrag (Art. 28 DSGVO) läuft demnächst ab:\n\n"
        f"  Partner: {avv.partner_name}\n"
        f"  Vertragsart: {partner_kind}\n"
        f"  Ablaufdatum: {avv.expiry_date.strftime('%d.%m.%Y')} (in {days_left} Tag(en))\n\n"
        f"Bitte erneuern oder kündigen Sie den Vertrag rechtzeitig.\n\n"
        f"-- Datenschutzagent"
    )
    return subject, body, {"days_left": days_left}


async def _load_notifiable_users(db: AsyncSession) -> dict[str, UserModel]:
    """Users with e-mail who have not opted out, keyed by lower-cased display name."""
    users_result = await db.execute(
        select(UserModel).where(UserModel.email.isnot(None))
    )
    return {
        u.display_name.lower(): u
        for u in users_result.scalars().all()
        if _user_accepts_notifications(u)
    }


async def scan_and_notify_deadlines(db: AsyncSession) -> dict:
    """Scannt Vorgänge, Datenpannen, DSR-Anfragen und AVV auf Fristen und sendet E-Mails.

    Returns summary dict with counts.
    """
    if not settings.smtp_enabled:
        logger.info("Deadline notifications skipped: SMTP not enabled")
        return {"sent": 0, "skipped_no_smtp": True}

    today = date.today()
    now_utc = datetime.now(UTC)
    cooldown = timedelta(hours=_NOTIFICATION_COOLDOWN_HOURS)
    users_by_name = await _load_notifiable_users(db)

    async def _rows(query):
        return (await db.execute(query)).scalars().all()

    active_cases = and_(
        CaseModel.archived_at.is_(None),
        CaseModel.status != CaseStatus.COMPLETED,
        CaseModel.deadline.isnot(None),
    )
    warning_date = today + timedelta(days=settings.notification_deadline_warning_days)
    breach_warning_dt = now_utc + timedelta(
        hours=settings.notification_breach_warning_hours
    )
    dsr_warning_date = today + timedelta(days=settings.notification_dsr_warning_days)
    avv_warning_date = today + timedelta(
        days=settings.notification_avv_expiry_warning_days
    )
    open_breaches = DataBreachModel.status.in_(["discovered", "assessed"])

    batches: list[tuple[str, Any, Callable[[Any, UserModel], _Message | None], Any]] = [
        (
            "deadline_warning",
            select(CaseModel).where(
                active_cases,
                CaseModel.deadline <= warning_date,
                CaseModel.deadline >= today,
            ),
            lambda c, u: _msg_case_deadline(c, u, today),
            _case_activity,
        ),
        (
            "deadline_overdue",
            select(CaseModel).where(active_cases, CaseModel.deadline < today),
            lambda c, u: _msg_case_overdue(c, u, today),
            _case_activity,
        ),
        (
            "breach_warning",
            select(DataBreachModel).where(
                open_breaches,
                DataBreachModel.notification_deadline.isnot(None),
                DataBreachModel.notification_deadline <= breach_warning_dt,
                DataBreachModel.notification_deadline >= now_utc,
            ),
            lambda b, u: _msg_breach_warning(b, u, now_utc),
            _breach_activity,
        ),
        (
            "breach_overdue",
            select(DataBreachModel).where(
                open_breaches, DataBreachModel.notification_deadline < now_utc
            ),
            lambda b, u: _msg_breach_overdue(b, u, now_utc),
            _breach_activity,
        ),
        (
            "dsr_warning",
            select(DSRRequestModel).where(
                DSRRequestModel.status.in_(["received", "in_progress"]),
                DSRRequestModel.response_deadline.isnot(None),
                DSRRequestModel.response_deadline <= dsr_warning_date,
                DSRRequestModel.response_deadline >= today,
            ),
            lambda d, u: _msg_dsr_warning(d, u, today),
            _dsr_activity,
        ),
        (
            "avv_expiry",
            select(AVVContractModel).where(
                AVVContractModel.status == "signed",
                AVVContractModel.expiry_date.isnot(None),
                AVVContractModel.expiry_date <= avv_warning_date,
                AVVContractModel.expiry_date >= today,
            ),
            lambda a, u: _msg_avv_expiry(a, u, today),
            None,  # AVV rows only carry the last_notified_at marker
        ),
    ]

    sent_count = 0
    for kind, query, build_message, make_activity in batches:
        sent_count += await _notify_entities(
            db,
            await _rows(query),
            users_by_name,
            now_utc=now_utc,
            cooldown=cooldown,
            kind=kind,
            build_message=build_message,
            make_activity=make_activity,
        )

    if sent_count > 0:
        await db.flush()

    logger.info("Deadline notification scan complete", extra={"sent": sent_count})
    return {"sent": sent_count}


# ---------------------------------------------------------------------------
# Item 15 — Neue Trigger
# ---------------------------------------------------------------------------


_SEVERITY_LABEL_DE = {
    FindingSeverity.CRITICAL: "Kritisch",
    FindingSeverity.HIGH: "Hoch",
    FindingSeverity.MEDIUM: "Mittel",
    FindingSeverity.LOW: "Niedrig",
    FindingSeverity.INFO: "Info",
}


async def scan_and_notify_critical_findings(db: AsyncSession) -> dict:
    """Sendet E-Mails für neue offene CRITICAL/HIGH-Findings, die noch nicht
    benachrichtigt wurden (findings.last_notified_at IS NULL) oder deren
    Cooldown abgelaufen ist.

    Adressat ist der Case-Assignee.
    """
    if not settings.smtp_enabled:
        logger.info("Critical-findings notifications skipped: SMTP not enabled")
        return {"sent": 0, "skipped_no_smtp": True}

    users_result = await db.execute(
        select(UserModel).where(UserModel.email != None)  # noqa: E711
    )
    users_by_name: dict[str, UserModel] = {}
    for u in users_result.scalars().all():
        if _user_accepts_notifications(u):
            users_by_name[u.display_name.lower()] = u

    now_utc = datetime.now(UTC)
    cooldown = timedelta(hours=_NOTIFICATION_COOLDOWN_HOURS)

    findings_result = await db.execute(
        select(FindingModel, CaseModel)
        .join(CaseModel, FindingModel.case_id == CaseModel.id)
        .where(
            and_(
                FindingModel.severity.in_(
                    [FindingSeverity.CRITICAL, FindingSeverity.HIGH]
                ),
                FindingModel.status == FindingStatus.OPEN,
                CaseModel.archived_at == None,  # noqa: E711
            )
        )
    )

    sent_count = 0
    for finding, case in findings_result.all():
        # Cooldown: bereits benachrichtigt und Cooldown noch aktiv?
        last = finding.last_notified_at
        if last and last.tzinfo is None:
            last = last.replace(tzinfo=UTC)
        if last and (now_utc - last) < cooldown:
            continue
        if not case.assignee:
            continue
        recipient = users_by_name.get(case.assignee.lower())
        if not recipient:
            logger.info(
                "critical_finding_notify skipped: assignee '%s' for finding %s has no notifiable user",
                case.assignee,
                finding.id,
            )
            continue

        severity_de = _SEVERITY_LABEL_DE.get(
            FindingSeverity(finding.severity), finding.severity
        )
        subject = f"[Datenschutzagent] {severity_de}: Befund in '{case.title}'"
        body = (
            f"Guten Tag {recipient.display_name},\n\n"
            f"im Vorgang '{case.title}' (Abteilung: {case.department or '–'}) gibt es einen "
            f"offenen Befund mit Schweregrad {severity_de}:\n\n"
            f"  Prüfung: {finding.check_name}\n"
            f"  Beschreibung: {(finding.description or '')[:500]}\n"
            f"  Kategorie: {finding.category}\n\n"
            f"Bitte prüfen und beheben Sie den Befund zeitnah.\n\n"
            f"-- Datenschutzagent"
        )
        if not recipient.email:
            continue
        try:
            await _send_email_async(recipient.email, subject, body)
            finding.last_notified_at = now_utc
            db.add(
                ActivityLogModel(
                    case_id=case.id,
                    event_type="notification_sent",
                    payload={
                        "type": "critical_finding",
                        "recipient_user_id": str(recipient.id),
                        "finding_id": str(finding.id),
                        "severity": finding.severity,
                    },
                )
            )
            sent_count += 1
        # One bad recipient must not kill the scan.
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Failed to send critical finding notification for finding %s: %s",
                finding.id,
                exc,
            )

    if sent_count > 0:
        await db.flush()

    logger.info(
        "Critical-finding notification scan complete", extra={"sent": sent_count}
    )
    return {"sent": sent_count}


async def scan_and_notify_maturity_decline(
    db: AsyncSession,
    *,
    threshold_pct: float | None = None,
    window_days: int | None = None,
) -> dict:
    """Sendet E-Mails an Admins, wenn der Compliance-Reife-Composite-Score
    einer Abteilung im Trend-Fenster (default risk_velocity.window_days) um
    mehr als die Signifikanz-Schwelle eingebrochen ist.

    Adressaten: alle Admin-Nutzer mit E-Mail + Notifications aktiv.
    Cooldown wird hier global pro Lauf gewährt (nicht pro Department), weil
    Admin-Benachrichtigungen ohnehin nur einmal täglich ausgelöst werden sollten.
    """
    if not settings.smtp_enabled:
        logger.info("Maturity-decline notifications skipped: SMTP not enabled")
        return {"sent": 0, "skipped_no_smtp": True}

    from app.services.maturity_service import compute_risk_velocity
    from app.services.risk_config_loader import get_risk_config

    cfg = get_risk_config().risk_velocity
    if not cfg.enabled:
        logger.info(
            "Maturity-decline notifications skipped: risk_velocity disabled in config"
        )
        return {"sent": 0, "skipped_disabled": True}

    velocity = await compute_risk_velocity(
        db,
        department=None,
        window_days=window_days if window_days is not None else cfg.window_days,
    )

    effective_threshold = (
        threshold_pct if threshold_pct is not None else cfg.significant_change_pct
    )
    declined = [
        d
        for d in velocity.get("departments", [])
        if d.get("trend") == "down"
        and d.get("delta") is not None
        and abs(d["delta"]) >= effective_threshold
    ]
    if not declined:
        logger.info("Maturity-decline scan: no significant declines detected")
        return {"sent": 0, "declines": 0}

    # Admin-Empfänger laden.
    admins_result = await db.execute(
        select(UserModel).where(
            and_(
                UserModel.email != None,  # noqa: E711
                UserModel.role == "admin",
            )
        )
    )
    recipients = [
        u for u in admins_result.scalars().all() if _user_accepts_notifications(u)
    ]
    if not recipients:
        logger.info("Maturity-decline scan: no admin recipients available")
        return {"sent": 0, "declines": len(declined), "skipped_no_recipients": True}

    lines = [
        "Folgende Abteilungen zeigen einen signifikanten Rückgang der Compliance-Reife:\n"
    ]
    for d in declined:
        lines.append(
            f"  - {d['department']}: {d['previous_composite']} -> {d['current_composite']} "
            f"(Delta {d['delta']:+.1f}, Fenster {velocity['window_days']}d)"
        )
    lines.append(
        f"\nSchwelle: {effective_threshold} Punkte. "
        "Details: /insights/velocity → Compliance-Reife-Trend."
    )
    body_text = "\n".join(lines)

    sent_count = 0
    for admin in recipients:
        subject = (
            f"[Datenschutzagent] Compliance-Reife eingebrochen "
            f"({len(declined)} Abteilung{'en' if len(declined) > 1 else ''})"
        )
        body = (
            f"Guten Tag {admin.display_name},\n\n"
            f"{body_text}\n\n"
            f"-- Datenschutzagent"
        )
        if not admin.email:
            continue
        try:
            await _send_email_async(admin.email, subject, body)
            sent_count += 1
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Failed to send maturity-decline notification to %s: %s",
                admin.email,
                exc,
            )

    logger.info(
        "Maturity-decline notification scan complete",
        extra={"sent": sent_count, "declines": len(declined)},
    )
    return {
        "sent": sent_count,
        "declines": len(declined),
        "departments": [d["department"] for d in declined],
    }
