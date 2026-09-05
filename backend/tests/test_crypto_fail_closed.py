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


# ---------------------------------------------------------------------------
# Phase 1 S7: key rotation (MultiFernet) and no silent plaintext fallback in production
# ---------------------------------------------------------------------------


def _keys(n: int) -> list[str]:
    from cryptography.fernet import Fernet

    return [Fernet.generate_key().decode() for _ in range(n)]


def test_old_key_still_decrypts_after_rotation(monkeypatch):
    from pydantic import SecretStr

    old, new = _keys(2)
    monkeypatch.setattr(settings, "app_environment", "production")
    monkeypatch.setattr(settings, "webhook_secret_encryption_key", SecretStr(old))
    ciphertext_old = crypto.encrypt_secret("hook-secret")

    crypto._fernet = None
    crypto._fernet_initialized = False
    monkeypatch.setattr(
        settings, "webhook_secret_encryption_key", SecretStr(f"{new},{old}")
    )
    assert crypto.decrypt_secret(ciphertext_old) == "hook-secret"
    rotated = crypto.rotate_secret(ciphertext_old)
    assert rotated != ciphertext_old
    assert crypto.decrypt_secret(rotated) == "hook-secret"

    # After dropping the old key the rotated value still works, the old one does not.
    crypto._fernet = None
    crypto._fernet_initialized = False
    monkeypatch.setattr(settings, "webhook_secret_encryption_key", SecretStr(new))
    assert crypto.decrypt_secret(rotated) == "hook-secret"
    with pytest.raises(RuntimeError, match="cannot be decrypted"):
        crypto.decrypt_secret(ciphertext_old)


def test_production_undecryptable_value_raises(monkeypatch):
    from pydantic import SecretStr

    monkeypatch.setattr(settings, "app_environment", "production")
    monkeypatch.setattr(
        settings, "webhook_secret_encryption_key", SecretStr(_keys(1)[0])
    )
    with pytest.raises(RuntimeError):
        crypto.decrypt_secret("legacy-plaintext-secret")


def test_development_undecryptable_value_falls_back_with_warning(monkeypatch, caplog):
    from pydantic import SecretStr

    monkeypatch.setattr(settings, "app_environment", "development")
    monkeypatch.setattr(
        settings, "webhook_secret_encryption_key", SecretStr(_keys(1)[0])
    )
    with caplog.at_level("WARNING", logger="app.core.crypto"):
        assert (
            crypto.decrypt_secret("legacy-plaintext-secret")
            == "legacy-plaintext-secret"
        )
    assert any("Klartext" in r.getMessage() for r in caplog.records)


def test_invalid_key_in_list_disables_encryption(monkeypatch):
    from pydantic import SecretStr

    monkeypatch.setattr(settings, "app_environment", "development")
    monkeypatch.setattr(
        settings, "webhook_secret_encryption_key", SecretStr(f"{_keys(1)[0]},not-a-key")
    )
    assert crypto._get_fernet() is None
