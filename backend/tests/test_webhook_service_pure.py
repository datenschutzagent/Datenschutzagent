"""Pure unit tests for webhook backoff and retry classification (no DB, no HTTP)."""
import random

from app.services import webhook_service


def test_backoff_delay_exponential_without_jitter(monkeypatch):
    monkeypatch.setattr(webhook_service.settings, "webhook_backoff_base_seconds", 2.0)
    monkeypatch.setattr(webhook_service.settings, "webhook_backoff_max_seconds", 30.0)
    monkeypatch.setattr(webhook_service.settings, "webhook_backoff_jitter", 0.0)

    assert webhook_service._backoff_delay(0) == 2.0
    assert webhook_service._backoff_delay(1) == 4.0
    assert webhook_service._backoff_delay(2) == 8.0
    assert webhook_service._backoff_delay(3) == 16.0


def test_backoff_delay_respects_max_cap(monkeypatch):
    monkeypatch.setattr(webhook_service.settings, "webhook_backoff_base_seconds", 2.0)
    monkeypatch.setattr(webhook_service.settings, "webhook_backoff_max_seconds", 10.0)
    monkeypatch.setattr(webhook_service.settings, "webhook_backoff_jitter", 0.0)

    # 2 * 2^3 = 16 > 10 → capped
    assert webhook_service._backoff_delay(3) == 10.0
    # very large attempt stays at cap
    assert webhook_service._backoff_delay(20) == 10.0


def test_backoff_delay_with_jitter_stays_in_range(monkeypatch):
    monkeypatch.setattr(webhook_service.settings, "webhook_backoff_base_seconds", 2.0)
    monkeypatch.setattr(webhook_service.settings, "webhook_backoff_max_seconds", 30.0)
    monkeypatch.setattr(webhook_service.settings, "webhook_backoff_jitter", 0.25)

    random.seed(42)
    # attempt_index=2 → base delay 8s, jitter ±25% → [6.0, 10.0]
    samples = [webhook_service._backoff_delay(2) for _ in range(50)]
    assert all(6.0 <= s <= 10.0 for s in samples), samples
    # non-trivial spread (not all identical)
    assert len(set(samples)) > 1


def test_backoff_delay_never_negative(monkeypatch):
    # Even extreme jitter cannot pull delay below 0
    monkeypatch.setattr(webhook_service.settings, "webhook_backoff_base_seconds", 0.0)
    monkeypatch.setattr(webhook_service.settings, "webhook_backoff_max_seconds", 0.0)
    monkeypatch.setattr(webhook_service.settings, "webhook_backoff_jitter", 1.0)

    for i in range(5):
        assert webhook_service._backoff_delay(i) >= 0.0


def test_is_retriable_status_5xx():
    assert webhook_service._is_retriable_status(500) is True
    assert webhook_service._is_retriable_status(502) is True
    assert webhook_service._is_retriable_status(503) is True
    assert webhook_service._is_retriable_status(599) is True


def test_is_retriable_status_retriable_4xx():
    assert webhook_service._is_retriable_status(408) is True
    assert webhook_service._is_retriable_status(425) is True
    assert webhook_service._is_retriable_status(429) is True


def test_is_retriable_status_non_retriable_4xx():
    assert webhook_service._is_retriable_status(400) is False
    assert webhook_service._is_retriable_status(401) is False
    assert webhook_service._is_retriable_status(403) is False
    assert webhook_service._is_retriable_status(404) is False
    assert webhook_service._is_retriable_status(422) is False


def test_sign_payload_deterministic():
    sig1 = webhook_service._sign_payload("secret123", b'{"event":"x"}')
    sig2 = webhook_service._sign_payload("secret123", b'{"event":"x"}')
    assert sig1 == sig2
    assert sig1.startswith("sha256=")
    # Different secret yields different signature
    assert webhook_service._sign_payload("other", b'{"event":"x"}') != sig1
