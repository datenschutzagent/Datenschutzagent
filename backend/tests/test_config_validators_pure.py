"""Pure unit tests for Settings validators (no DB, no SMTP needed)."""
import logging

from app.config import Settings


def test_timeout_warning_logged_when_check_lt_ollama(caplog):
    caplog.set_level(logging.WARNING, logger="app.startup")
    Settings(llm_provider="ollama", check_timeout_seconds=30.0, ollama_timeout_seconds=120.0)
    messages = [r.message for r in caplog.records if "timeout misconfiguration" in r.message.lower()]
    assert messages, "expected timeout misconfiguration warning"


def test_no_timeout_warning_when_check_ge_ollama(caplog):
    caplog.set_level(logging.WARNING, logger="app.startup")
    Settings(llm_provider="ollama", check_timeout_seconds=180.0, ollama_timeout_seconds=120.0)
    messages = [r.message for r in caplog.records if "timeout misconfiguration" in r.message.lower()]
    assert not messages


def test_no_timeout_warning_when_check_disabled(caplog):
    caplog.set_level(logging.WARNING, logger="app.startup")
    Settings(llm_provider="ollama", check_timeout_seconds=0.0, ollama_timeout_seconds=120.0)
    messages = [r.message for r in caplog.records if "timeout misconfiguration" in r.message.lower()]
    assert not messages


def test_no_timeout_warning_for_non_ollama_provider(caplog):
    caplog.set_level(logging.WARNING, logger="app.startup")
    Settings(llm_provider="openai", check_timeout_seconds=30.0, ollama_timeout_seconds=120.0)
    messages = [r.message for r in caplog.records if "timeout misconfiguration" in r.message.lower()]
    assert not messages
