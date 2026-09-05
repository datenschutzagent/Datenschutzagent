"""Hilfsfunktionen zur symmetrischen Verschlüsselung sensibler Felder (z.B. Webhook-Secrets).

Verwendet Fernet (AES-128-CBC + HMAC-SHA256) aus dem cryptography-Paket.

Key-Rotation: ``WEBHOOK_SECRET_ENCRYPTION_KEY`` darf eine kommagetrennte Liste sein.
Der **erste** Schlüssel verschlüsselt neue Werte, alle weiteren werden nur noch zum
Entschlüsseln akzeptiert (``MultiFernet``). Ablauf einer Rotation:

1. neuen Schlüssel *vorn* anhängen: ``NEU,ALT``
2. deployen → neue Secrets nutzen NEU, alte bleiben lesbar
3. ``rotate_secret()`` über Bestandsdaten laufen lassen (CLI/Job)
4. ``ALT`` aus der Liste entfernen

Falls kein Schlüssel gesetzt ist, werden die Funktionen außerhalb von production als
No-Op ausgeführt (Klartext bleibt erhalten), um lokale Setups nicht zu brechen.

Einen gültigen Fernet-Schlüssel erzeugt man einmalig mit:
    python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
"""

import logging

from app.config import settings

logger = logging.getLogger(__name__)

_fernet = None
_fernet_initialized = False


def _configured_keys() -> list[str]:
    raw = settings.webhook_secret_encryption_key.get_secret_value() or ""
    return [k.strip() for k in raw.split(",") if k.strip()]


def _get_fernet():
    """Gibt die MultiFernet-Instanz zurück; None wenn kein Schlüssel konfiguriert ist."""
    global _fernet, _fernet_initialized
    if _fernet_initialized:
        return _fernet
    _fernet_initialized = True
    keys = _configured_keys()
    if not keys:
        return None
    try:
        from cryptography.fernet import Fernet, MultiFernet

        _fernet = MultiFernet([Fernet(k.encode()) for k in keys])
    except Exception as exc:
        logger.error(
            "Ungültiger WEBHOOK_SECRET_ENCRYPTION_KEY: %s – Verschlüsselung deaktiviert.",
            exc,
        )
        _fernet = None
    return _fernet


def _missing_key_error() -> RuntimeError:
    return RuntimeError(
        "WEBHOOK_SECRET_ENCRYPTION_KEY must be set in production — refusing to "
        "store webhook secrets in plaintext. Generate a key with: "
        'python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"'
    )


def encrypt_secret(plaintext: str) -> str:
    """Verschlüsselt einen Klartext-String mit dem ersten (aktiven) Schlüssel.

    In Produktion (``APP_ENVIRONMENT=production``) muss ein Fernet-Schlüssel
    konfiguriert sein; andernfalls wird ein ``RuntimeError`` geworfen, damit
    keine Klartext-Secrets in der DB landen. In Entwicklungs-/Testumgebungen
    bleibt das lockere Verhalten erhalten: fehlt der Schlüssel, wird der
    Klartext unverändert zurückgegeben.
    """
    if not plaintext:
        return plaintext
    fernet = _get_fernet()
    if fernet is None:
        if settings.app_environment == "production":
            raise _missing_key_error()
        return plaintext
    return fernet.encrypt(plaintext.encode()).decode()


def decrypt_secret(ciphertext: str) -> str:
    """Entschlüsselt einen Wert mit einem der konfigurierten Schlüssel.

    Schlägt die Entschlüsselung fehl (falscher/rotierter Schlüssel oder ein noch
    unverschlüsselter Altbestand), gilt: in production ist das ein Fehler – ein
    stiller Klartext-Fallback würde einen manipulierten oder verlorenen Schlüssel
    verschleiern. Außerhalb von production wird der Wert mit WARNING-Log unverändert
    zurückgegeben (Altbestand vor Einführung der Verschlüsselung).
    """
    if not ciphertext:
        return ciphertext
    fernet = _get_fernet()
    if fernet is None:
        return ciphertext
    try:
        return fernet.decrypt(ciphertext.encode()).decode()
    except Exception as exc:
        if settings.app_environment == "production":
            raise RuntimeError(
                "decrypt_secret: value cannot be decrypted with any configured "
                "WEBHOOK_SECRET_ENCRYPTION_KEY (rotated/lost key or legacy plaintext)."
            ) from exc
        logger.warning(
            "decrypt_secret: Fallback auf Klartext (Wert nicht mit den konfigurierten "
            "Schlüsseln entschlüsselbar – Altbestand?)."
        )
        return ciphertext


def rotate_secret(ciphertext: str) -> str:
    """Re-encrypt a stored value with the active (first) key; no-op without keys."""
    if not ciphertext:
        return ciphertext
    fernet = _get_fernet()
    if fernet is None:
        return ciphertext
    return fernet.rotate(ciphertext.encode()).decode()
