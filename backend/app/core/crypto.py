"""Hilfsfunktionen zur symmetrischen Verschlüsselung sensibler Felder (z.B. Webhook-Secrets).

Verwendet Fernet (AES-128-CBC + HMAC-SHA256) aus dem cryptography-Paket.
Falls WEBHOOK_SECRET_ENCRYPTION_KEY nicht gesetzt ist, werden die Funktionen
als No-Op ausgeführt (Klartext bleibt erhalten), um bestehende Deployments
nicht zu brechen.

Einen gültigen Fernet-Schlüssel erzeugt man einmalig mit:
    python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
"""

import logging

from app.config import settings

logger = logging.getLogger(__name__)

_fernet = None
_fernet_initialized = False


def _get_fernet():
    """Gibt die Fernet-Instanz zurück; None wenn kein Schlüssel konfiguriert ist."""
    global _fernet, _fernet_initialized
    if _fernet_initialized:
        return _fernet
    _fernet_initialized = True
    key = (settings.webhook_secret_encryption_key.get_secret_value() or "").strip()
    if not key:
        return None
    try:
        from cryptography.fernet import Fernet

        _fernet = Fernet(key.encode())
    except Exception as exc:
        logger.error(
            "Ungültiger WEBHOOK_SECRET_ENCRYPTION_KEY: %s – Verschlüsselung deaktiviert.",
            exc,
        )
        _fernet = None
    return _fernet


def encrypt_secret(plaintext: str) -> str:
    """Verschlüsselt einen Klartext-String.

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
            raise RuntimeError(
                "WEBHOOK_SECRET_ENCRYPTION_KEY must be set in production — refusing to "
                "store webhook secrets in plaintext. Generate a key with: "
                'python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"'
            )
        return plaintext
    return fernet.encrypt(plaintext.encode()).decode()


def decrypt_secret(ciphertext: str) -> str:
    """Entschlüsselt einen verschlüsselten String. Gibt den String unverändert zurück,
    wenn kein Schlüssel konfiguriert ist oder der Wert bereits im Klartext vorliegt."""
    if not ciphertext:
        return ciphertext
    fernet = _get_fernet()
    if fernet is None:
        return ciphertext
    try:
        return fernet.decrypt(ciphertext.encode()).decode()
    except Exception:
        # Fallback: Wert liegt noch im Klartext vor (z.B. vor Migration)
        logger.debug(
            "decrypt_secret: Fallback auf Klartext (Wert ist noch nicht verschlüsselt)."
        )
        return ciphertext
