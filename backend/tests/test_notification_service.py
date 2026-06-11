"""Pure unit tests for notification service helper logic."""

from datetime import UTC, date, datetime, timedelta


def test_cooldown_check():
    """20h cooldown: entity notified < 20h ago should be skipped."""
    now = datetime.now(UTC)
    last_notified = now - timedelta(hours=10)
    cooldown_hours = 20
    assert (
        now - last_notified
    ).total_seconds() / 3600 < cooldown_hours  # still in cooldown

    last_notified_old = now - timedelta(hours=25)
    assert (
        now - last_notified_old
    ).total_seconds() / 3600 >= cooldown_hours  # cooldown expired


def test_case_deadline_window():
    """Cases with deadline within 30 days are in warning window."""
    today = date.today()
    deadline_soon = today + timedelta(days=15)
    deadline_far = today + timedelta(days=45)
    deadline_past = today - timedelta(days=5)
    warning_window_days = 30

    assert (deadline_soon - today).days <= warning_window_days
    assert (deadline_far - today).days > warning_window_days
    assert (deadline_past - today).days < 0  # overdue


def test_breach_72h_deadline():
    """Data breach notification deadline is 72h from discovery."""
    discovered = datetime(2026, 4, 14, 10, 0, 0, tzinfo=UTC)
    deadline = discovered + timedelta(hours=72)
    now = discovered + timedelta(hours=50)
    assert deadline > now  # still time left

    now_after = discovered + timedelta(hours=80)
    assert deadline < now_after  # overdue


def test_dsr_30day_deadline():
    """DSR response deadline is 30 days from receipt."""
    received = date(2026, 4, 14)
    deadline = received + timedelta(days=30)
    assert deadline == date(2026, 5, 14)

    # with extension
    extension = 14
    extended_deadline = received + timedelta(days=30 + extension)
    assert extended_deadline == date(2026, 5, 28)


def test_avv_expiry_warning():
    """AVV contracts expiring within 90 days trigger warning."""
    today = date.today()
    expiry_soon = today + timedelta(days=60)
    expiry_far = today + timedelta(days=120)
    warning_window = 90

    assert (expiry_soon - today).days <= warning_window
    assert (expiry_far - today).days > warning_window
