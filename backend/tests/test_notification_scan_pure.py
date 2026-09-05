"""Pure tests for the generic deadline-notification loop and its message builders.

No database: entities are ``SimpleNamespace`` objects, the SMTP send is stubbed and
``db.add`` is captured by a fake session. Covers the behaviour that the decomposed
``scan_and_notify_deadlines`` (Qualitätsplan Phase 2 R7) relies on.
"""

import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from app.services import notification_service as ns

NOW = datetime(2026, 9, 5, 12, 0, tzinfo=UTC)
TODAY = NOW.date()
COOLDOWN = timedelta(hours=20)


class _FakeDb:
    def __init__(self) -> None:
        self.added: list = []

    def add(self, obj) -> None:
        self.added.append(obj)


def _user(name: str = "Anna", email: str | None = "anna@example.com"):
    return SimpleNamespace(
        id=uuid.uuid4(), display_name=name, email=email, notifications_enabled=True
    )


def _entity(assignee: str | None = "Anna", last_notified_at=None):
    return SimpleNamespace(
        id=uuid.uuid4(), assignee=assignee, last_notified_at=last_notified_at
    )


def _message(entity, user):
    return ("subject", "body", {"extra": 1})


@pytest.fixture
def sent(monkeypatch):
    calls: list[tuple[str, str, str]] = []

    async def _fake_send(to, subject, body):
        calls.append((to, subject, body))

    monkeypatch.setattr(ns, "_send_email_async", _fake_send)
    return calls


async def _run(db, entities, users, make_activity=None, build_message=_message):
    return await ns._notify_entities(
        db,
        entities,
        users,
        now_utc=NOW,
        cooldown=COOLDOWN,
        kind="deadline_warning",
        build_message=build_message,
        make_activity=make_activity,
    )


async def test_sends_marks_and_records_activity(sent):
    db = _FakeDb()
    user = _user()
    entity = _entity()
    captured = {}

    def _activity(e, payload):
        captured["entity"] = e
        captured["payload"] = payload
        return "activity-row"

    count = await _run(db, [entity], {"anna": user}, make_activity=_activity)

    assert count == 1
    assert sent == [("anna@example.com", "subject", "body")]
    assert entity.last_notified_at == NOW
    assert db.added == ["activity-row"]
    assert captured["entity"] is entity
    assert captured["payload"] == {
        "type": "deadline_warning",
        "recipient_user_id": str(user.id),
        "extra": 1,
    }


async def test_skips_without_assignee_or_unknown_user(sent):
    db = _FakeDb()
    entities = [_entity(assignee=None), _entity(assignee="Nobody")]
    count = await _run(db, entities, {"anna": _user()})
    assert count == 0
    assert sent == []
    assert all(e.last_notified_at is None for e in entities)


async def test_assignee_lookup_is_case_insensitive(sent):
    count = await _run(_FakeDb(), [_entity(assignee="ANNA")], {"anna": _user()})
    assert count == 1


async def test_cooldown_skips_recent_but_not_expired(sent):
    recent = _entity(last_notified_at=NOW - timedelta(hours=5))
    # Naive legacy timestamp is interpreted as UTC.
    expired = _entity(last_notified_at=(NOW - timedelta(hours=25)).replace(tzinfo=None))
    count = await _run(_FakeDb(), [recent, expired], {"anna": _user()})
    assert count == 1
    assert recent.last_notified_at == NOW - timedelta(hours=5)
    assert expired.last_notified_at == NOW


async def test_builder_returning_none_skips_entity(sent):
    count = await _run(
        _FakeDb(), [_entity()], {"anna": _user()}, build_message=lambda e, u: None
    )
    assert count == 0
    assert sent == []


async def test_failed_send_does_not_abort_scan(monkeypatch):
    attempts: list[str] = []

    async def _flaky(to, subject, body):
        attempts.append(to)
        if len(attempts) == 1:
            raise OSError("smtp down")

    monkeypatch.setattr(ns, "_send_email_async", _flaky)
    first, second = _entity(), _entity()
    db = _FakeDb()
    count = await _run(
        db, [first, second], {"anna": _user()}, make_activity=lambda e, p: p
    )

    assert count == 1
    assert first.last_notified_at is None  # failed send leaves the marker untouched
    assert second.last_notified_at == NOW
    assert len(db.added) == 1


async def test_without_activity_factory_only_marker_is_set(sent):
    db = _FakeDb()
    entity = _entity()
    count = await _run(db, [entity], {"anna": _user()}, make_activity=None)
    assert count == 1
    assert db.added == []
    assert entity.last_notified_at == NOW


# ---------------------------------------------------------------------------
# Message builders
# ---------------------------------------------------------------------------


def test_case_deadline_builder_counts_days_and_handles_missing_deadline():
    user = _user()
    case = SimpleNamespace(
        title="CRM", department="IT", deadline=TODAY + timedelta(days=3)
    )
    subject, body, payload = ns._msg_case_deadline(case, user, TODAY)
    assert "in 3 Tag(en)" in subject
    assert "CRM" in body and "Anna" in body
    assert payload == {"days_left": 3}

    case.deadline = None
    assert ns._msg_case_deadline(case, user, TODAY) is None
    assert ns._msg_case_overdue(case, user, TODAY) is None


def test_case_overdue_builder():
    case = SimpleNamespace(
        title="Alt", department="HR", deadline=TODAY - timedelta(days=7)
    )
    subject, _body, payload = ns._msg_case_overdue(case, _user(), TODAY)
    assert "ÜBERFÄLLIG (7d)" in subject
    assert payload == {"days_overdue": 7}


def test_breach_builders_use_hours_and_clamp_at_zero():
    breach = SimpleNamespace(
        title="Leak", notification_deadline=NOW + timedelta(hours=5)
    )
    subject, _body, payload = ns._msg_breach_warning(breach, _user(), NOW)
    assert "in 5h" in subject
    assert payload == {"hours_left": 5}

    breach.notification_deadline = NOW - timedelta(hours=30)
    subject, _body, payload = ns._msg_breach_overdue(breach, _user(), NOW)
    assert "(30h)" in subject
    assert payload == {"hours_overdue": 30}
    # A warning for an already-passed deadline never reports negative hours.
    assert ns._msg_breach_warning(breach, _user(), NOW)[2] == {"hours_left": 0}


def test_dsr_builder_translates_request_type():
    dsr = SimpleNamespace(
        request_type="erasure",
        requestor_name=None,
        response_deadline=TODAY + timedelta(days=2),
    )
    subject, body, payload = ns._msg_dsr_warning(dsr, _user(), TODAY)
    assert "(Löschung)" in subject
    assert "(unbekannt)" in body
    assert payload == {"days_left": 2}

    dsr.request_type = "custom"
    assert "(custom)" in ns._msg_dsr_warning(dsr, _user(), TODAY)[0]


def test_avv_builder_labels_partner_type():
    avv = SimpleNamespace(
        partner_name="Cloud GmbH",
        partner_type="processor",
        expiry_date=TODAY + timedelta(days=10),
    )
    _subject, body, payload = ns._msg_avv_expiry(avv, _user(), TODAY)
    assert "Auftragsverarbeiter" in body
    assert payload == {"days_left": 10}

    avv.partner_type = "sub_processor"
    assert "Unter-AV" in ns._msg_avv_expiry(avv, _user(), TODAY)[1]
    avv.expiry_date = None
    assert ns._msg_avv_expiry(avv, _user(), TODAY) is None


def test_normalize_ts():
    naive = datetime(2026, 1, 1, 8, 0)
    assert ns._normalize_ts(naive) == naive.replace(tzinfo=UTC)
    assert ns._normalize_ts(NOW) is NOW
    assert ns._normalize_ts(None) is None


def test_user_accepts_notifications_respects_opt_out():
    assert ns._user_accepts_notifications(None) is False
    assert ns._user_accepts_notifications(_user(email=None)) is False
    assert ns._user_accepts_notifications(_user()) is True
    opted_out = _user()
    opted_out.notifications_enabled = False
    assert ns._user_accepts_notifications(opted_out) is False
