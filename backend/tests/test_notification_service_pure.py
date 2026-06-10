"""Pure unit tests for notification_service helpers (no DB)."""

from __future__ import annotations

from app.services.notification_service import _user_accepts_notifications


class _StubUser:
    def __init__(self, email: str | None, notifications_enabled: bool = True):
        self.email = email
        self.notifications_enabled = notifications_enabled


class _LegacyUser:
    """Simulates older UserModel rows that lack the new column attribute."""

    def __init__(self, email: str | None):
        self.email = email


def test_accepts_user_with_email_and_enabled():
    assert _user_accepts_notifications(_StubUser("dpo@example.org", True)) is True


def test_rejects_user_with_disabled_flag():
    assert _user_accepts_notifications(_StubUser("dpo@example.org", False)) is False


def test_rejects_user_without_email():
    assert _user_accepts_notifications(_StubUser(None, True)) is False


def test_rejects_user_with_empty_email():
    assert _user_accepts_notifications(_StubUser("", True)) is False


def test_rejects_none():
    assert _user_accepts_notifications(None) is False


def test_legacy_user_defaults_to_enabled():
    """Backward-compat: alte Fixtures ohne das Attribut sollen nicht stillschweigend gemutet werden."""
    assert _user_accepts_notifications(_LegacyUser("dpo@example.org")) is True


def test_legacy_user_without_email_still_rejected():
    assert _user_accepts_notifications(_LegacyUser(None)) is False


def test_severity_label_mapping_is_complete():
    """Sicherheits-Test: alle FindingSeverity-Werte haben eine deutsche Übersetzung."""
    from app.constants import FindingSeverity
    from app.services.notification_service import _SEVERITY_LABEL_DE

    for sev in FindingSeverity:
        assert (
            sev in _SEVERITY_LABEL_DE
        ), f"FindingSeverity.{sev.name} fehlt in _SEVERITY_LABEL_DE"
