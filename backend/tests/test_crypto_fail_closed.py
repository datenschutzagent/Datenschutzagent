"""Ensures webhook secret encryption fails closed in production.

``encrypt_secret`` must refuse to return plaintext when
``APP_ENVIRONMENT=production`` and no Fernet key is configured; in
development / test it remains lenient so that local workflows continue to
function without the extra setup step.
"""

from __future__ import annotations

import pytest

import app.core.crypto as crypto
from app.config import settings


@pytest.fixture(autouse=True)
def _reset_fernet_singleton():
    """Reset the module-global Fernet cache around each test."""
    crypto._fernet = None
    crypto._fernet_initialized = False
    yield
    crypto._fernet = None
    crypto._fernet_initialized = False


def test_production_without_key_raises(monkeypatch):
    monkeypatch.setattr(settings, "app_environment", "production")
    from pydantic import SecretStr

    monkeypatch.setattr(settings, "webhook_secret_encryption_key", SecretStr(""))
    with pytest.raises(RuntimeError, match="WEBHOOK_SECRET_ENCRYPTION_KEY"):
        crypto.encrypt_secret("my-secret")


def test_production_with_key_encrypts(monkeypatch):
    from cryptography.fernet import Fernet
    from pydantic import SecretStr

    key = Fernet.generate_key().decode()
    monkeypatch.setattr(settings, "app_environment", "production")
    monkeypatch.setattr(settings, "webhook_secret_encryption_key", SecretStr(key))
    ciphertext = crypto.encrypt_secret("my-secret")
    assert ciphertext != "my-secret"
    assert crypto.decrypt_secret(ciphertext) == "my-secret"


def test_development_without_key_returns_plaintext(monkeypatch):
    from pydantic import SecretStr

    monkeypatch.setattr(settings, "app_environment", "development")
    monkeypatch.setattr(settings, "webhook_secret_encryption_key", SecretStr(""))
    assert crypto.encrypt_secret("my-secret") == "my-secret"


def test_test_environment_without_key_returns_plaintext(monkeypatch):
    from pydantic import SecretStr

    monkeypatch.setattr(settings, "app_environment", "test")
    monkeypatch.setattr(settings, "webhook_secret_encryption_key", SecretStr(""))
    assert crypto.encrypt_secret("my-secret") == "my-secret"


def test_empty_plaintext_passes_through_in_any_environment(monkeypatch):
    from pydantic import SecretStr

    monkeypatch.setattr(settings, "app_environment", "production")
    monkeypatch.setattr(settings, "webhook_secret_encryption_key", SecretStr(""))
    # Empty string short-circuits before the production check — callers rely
    # on this to avoid serializing empty optional secrets.
    assert crypto.encrypt_secret("") == ""
