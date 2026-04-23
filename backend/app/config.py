"""Application configuration."""
from __future__ import annotations

import urllib.parse
from typing import Literal

from pydantic import SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Settings loaded from environment."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        repr=False,  # prevent accidental secret leakage in logs
    )

    app_name: str = "Datenschutzagent API"
    debug: bool = False

    # Deployment environment — required. ``production`` triggers a stricter
    # validator cascade (OIDC mandatory, webhook encryption key mandatory,
    # HTTPS-only CORS). No default on purpose: forgetting to set it must fail
    # the container startup rather than silently booting with permissive rules.
    app_environment: Literal["development", "test", "production"]

    # API
    api_v1_prefix: str = "/api/v1"

    # Database (F5: no default credentials — must be set via DATABASE_URL env var)
    database_url: str = ""

    # Celery (Redis as broker; worker uses sync DB). If empty, document extraction runs synchronously.
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_enabled: bool = True  # Set False or leave broker empty to skip async extraction

    # Storage (MinIO/S3 or local path)
    storage_backend: str = "local"
    storage_local_path: str = "./storage"
    s3_endpoint_url: str | None = None
    s3_access_key: str | None = None
    s3_secret_key: str | None = None
    s3_bucket: str = "documents"

    # CORS (in .env als kommagetrennte Liste, z. B. CORS_ORIGINS=http://localhost:3002)
    # Production: set to your exact HTTPS frontend origin, e.g. https://datenschutzagent.example.com
    cors_origins: str | list[str] = ["http://localhost:3002", "http://127.0.0.1:3002", "http://localhost:5173", "http://127.0.0.1:5173"]

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: str | list[str]) -> list[str]:
        if isinstance(v, list):
            items = v
        else:
            items = [x.strip() for x in str(v).split(",") if x.strip()]
        # Reject obvious misconfigurations (wildcards, regex chars, empty scheme) that would
        # open CSRF surface. Exact scheme://host[:port] only.
        for origin in items:
            if origin == "*" or "*" in origin:
                raise ValueError(f"CORS_ORIGINS wildcard not allowed: {origin!r}")
            if any(c in origin for c in ("?", "(", ")", "[", "]", "{", "}", "^", "$", "\\")):
                raise ValueError(f"CORS_ORIGINS regex/special chars not allowed: {origin!r}")
            p = urllib.parse.urlparse(origin)
            if p.scheme not in ("http", "https") or not p.netloc or p.path not in ("", "/"):
                raise ValueError(
                    f"CORS_ORIGINS must be 'scheme://host[:port]' only, got: {origin!r}"
                )
        return items

    # Reverse-proxy / load-balancer peers whose X-Forwarded-For header the rate limiter
    # should trust. Comma-separated list of exact IPs or CIDR ranges (e.g.
    # "10.0.0.0/8,192.168.1.5"). Empty = only the direct socket peer IP is used.
    trusted_proxies: str | list[str] = ""

    @field_validator("trusted_proxies", mode="before")
    @classmethod
    def parse_trusted_proxies(cls, v: str | list[str]) -> list[str]:
        if isinstance(v, list):
            items = v
        else:
            items = [x.strip() for x in str(v).split(",") if x.strip()]
        import ipaddress as _ip
        for entry in items:
            try:
                _ip.ip_network(entry, strict=False)
            except ValueError as exc:
                raise ValueError(
                    f"TRUSTED_PROXIES entry {entry!r} is not a valid IP or CIDR range: {exc}"
                ) from exc
        return items

    # Playbook seed (YAML directory; used when playbooks table is empty)
    playbooks_seed_dir: str | None = None  # None = use default app/data/playbooks

    # Organisation units (dropdown / case.department): YAML source
    # If set, this file is used (absolute path or relative to app data dir, e.g. org_profiles/acme/departments.yaml).
    departments_config_path: str | None = None
    # If departments_config_path is empty: use data/org_profiles/{org_profile}/departments.yaml when it exists, else data/fachbereiche.yaml
    org_profile: str = "default"

    # Organisation display name shown in the frontend header.
    # Falls back to org_profiles/{org_profile}/profile.yaml -> org_name if empty.
    org_name: str = ""

    # Default user display name (created on first startup when OIDC is disabled).
    default_user_display_name: str = "Standardnutzer"

    # Comma-separated processing context options for the new-case dialog.
    # Each entry: "value:Label" (e.g. "research:Forschung,hr:Personal").
    # Empty = use built-in defaults.
    processing_context_options: str = ""

    # Semicolon-separated VVT canonical field names.
    # Overrides org_profiles/{org_profile}/profile.yaml -> vvt_fields if set.
    # Empty = use profile.yaml or built-in DSGVO Art. 30 defaults.
    vvt_field_names: str = ""

    # Dokument-Upload: maximale Dateigröße in Bytes (Standard: 50 MB; via MAX_UPLOAD_SIZE_BYTES überschreibbar)
    max_upload_size_bytes: int = 52428800

    # Periodischer Recheck: Verzögerung in Sekunden zwischen gestaffelten Celery-Jobs (verhindert Lastspitzen)
    run_checks_stagger_seconds: int = 30

    # Retention / Auto-Archivierung (DSGVO Art. 5 Abs. 1 lit. e – Speicherbegrenzung)
    # True (default): Es werden NUR Vorgänge archiviert, die completed_at gesetzt haben.
    # False: Fallback auf created_at (alte Vorgänge auch ohne Abschluss werden archiviert).
    retention_require_completed: bool = True
    # Vorlaufzeit in Tagen: Vorgänge, deren Aufbewahrungsfrist in <= N Tagen abläuft,
    # erscheinen im Warn-Scan (scan_cases_due_for_retention_warning) und können
    # via Benachrichtigung angekündigt werden.
    retention_grace_days: int = 14

    # LLM context limits (chars per document; lower = faster/cheaper, higher = more context)
    max_context_chars_per_doc: int = 15000  # single-doc full-text context window limit
    max_context_chars_rag: int = 20000       # assembled RAG context limit
    max_context_chars_vvt: int = 25000       # VVT/ROPA normalization context limit (higher because ROPA docs can be large)

    # Maximale Anzahl gleichzeitiger LLM-Anfragen pro run_checks-Job.
    # Verhindert Überlastung von Ollama und Rate-Limit-Fehler bei OpenAI/Anthropic.
    # 0 = kein Limit (nicht empfohlen für lokales Ollama).
    max_concurrent_llm_calls: int = 2

    # Timeout pro Prüfung in Sekunden (asyncio.wait_for um _do()).
    # Muss >= ollama_timeout_seconds sein, damit der HTTP-Call noch sauber abbrechen kann.
    # 0 = deaktiviert (nicht empfohlen bei lokalem Ollama, da hängende Requests den Job blockieren).
    check_timeout_seconds: float = 180.0

    # Standard-Strategien für automatische Re-Checks (auto_run_checks, periodic_recheck).
    # Kommagetrennt: "full_text", "rag" oder "full_text,rag"
    recheck_default_strategies: str = "full_text"

    # Ollama (extern gehostet, z. B. im lokalen Netzwerk)
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2"
    ollama_timeout_seconds: float = 120.0
    ollama_enabled: bool = True

    # OCR via Ollama Vision (gescannte PDFs; z. B. qwen2.5-vl, minicpm-v)
    ollama_ocr_model: str = "qwen2.5-vl"
    ollama_ocr_enabled: bool = True
    ocr_min_chars_per_page: int = 50  # below this avg chars/page → use OCR fallback
    ocr_dpi: int = 150  # resolution for PDF page images sent to vision model
    ocr_max_pages: int = 200  # max pages to process with OCR (prevents memory exhaustion)

    # Current user (optional UUID; if unset, default user is used for GET/PATCH /me when OIDC is disabled)
    current_user_id: str | None = None

    # OAuth2/OIDC (optional; when enabled, Bearer token required for protected routes)
    oidc_enabled: bool = False
    oidc_issuer_url: str = ""  # e.g. https://auth.example.com/realms/datenschutzagent
    oidc_client_id: str = ""
    oidc_client_secret: SecretStr = SecretStr("")  # For token introspection / backend flows; can be empty for public clients
    oidc_audience: str | None = None  # Optional; if set, JWT aud claim must match
    oidc_scopes: str = "openid profile email"  # Space-separated

    # RBAC: default role for new users (viewer, editor, admin). Existing users updated by migration.
    rbac_default_role: str = "viewer"

    # Session-cookie auth (feature flag). When enabled, /api/v1/auth/session
    # exchanges OIDC authorization codes for an HttpOnly session cookie + a
    # readable CSRF cookie. The legacy Bearer-token flow keeps working so
    # deployments can roll the change out gradually.
    auth_session_cookie_enabled: bool = False
    session_ttl_seconds: int = 43200  # 12h sliding session
    # Cookie names. The ``__Host-`` prefix mandates Secure + no Domain + Path=/
    # and is only usable over HTTPS, so we drop it in non-production so
    # browsers accept the cookie on plain-HTTP dev setups.
    session_cookie_name_production: str = "__Host-ds_session"
    session_cookie_name_development: str = "ds_session"
    csrf_cookie_name_production: str = "__Host-ds_csrf"
    csrf_cookie_name_development: str = "ds_csrf"

    # LLM response cache (Redis; avoids re-running identical checks on unchanged documents)
    llm_cache_enabled: bool = False  # set True to activate; requires Redis (celery_broker_url)
    llm_cache_ttl: int = 86400       # seconds (default: 24 h)

    # SMTP / E-Mail-Benachrichtigungen (optional)
    smtp_enabled: bool = False
    smtp_host: str = "localhost"
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: SecretStr = SecretStr("")
    smtp_from_address: str = "datenschutzagent@example.org"
    smtp_tls: bool = True
    notification_deadline_warning_days: int = 7        # Warnung X Tage vor Vorgangs-Fristablauf
    notification_breach_warning_hours: int = 12        # Warnung X Stunden vor Datenpannen-Meldepflicht
    notification_dsr_warning_days: int = 5             # Warnung X Tage vor DSR-Antwortpflicht
    notification_avv_expiry_warning_days: int = 90     # Warnung X Tage vor AVV-Ablauf

    # Prompt injection protection: when True, requests containing injection patterns are
    # rejected with an exception instead of just logged. True = block (default); set False
    # only if you need to allow edge-case content that triggers false positives.
    prompt_injection_block: bool = True

    # LLM-Provider (ollama | openai | anthropic)
    # Ollama-Konfiguration bleibt unverändert (ollama_base_url, ollama_model, etc.)
    llm_provider: str = "ollama"      # Aktiver Provider: "ollama", "openai" oder "anthropic"
    openai_api_key: SecretStr = SecretStr("")  # OpenAI API-Key (wenn llm_provider=openai)
    openai_model: str = "gpt-4o-mini"
    anthropic_api_key: SecretStr = SecretStr("")  # Anthropic API-Key (wenn llm_provider=anthropic)
    anthropic_model: str = "claude-3-5-haiku-latest"  # Anthropic-Modell

    # Webhook-Benachrichtigungen (ausgehend)
    webhook_max_retries: int = 3          # Anzahl Wiederholungsversuche bei Fehler
    webhook_timeout_seconds: float = 10.0 # HTTP-Timeout pro Versuch
    # Basiswartezeit (Sekunden) für exponentielles Backoff: 2s → 4s → 8s → 16s
    webhook_backoff_base_seconds: float = 2.0
    # Oberes Limit für Wartezeiten zwischen Retries (Sekunden)
    webhook_backoff_max_seconds: float = 30.0
    # Jitter (0.0–1.0): zufälliger Anteil der Wartezeit, um synchrones Hämmern zu vermeiden
    webhook_backoff_jitter: float = 0.25
    # Fernet-Schlüssel zur Verschlüsselung von Webhook-Secrets in der DB (optional).
    # Erzeugen: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    # Leer lassen = Secrets werden unverschlüsselt gespeichert (Rückwärtskompatibilität).
    webhook_secret_encryption_key: SecretStr = SecretStr("")

    # Weaviate (optional; RAG document checks)
    weaviate_url: str = "http://localhost:8080"
    weaviate_api_key: SecretStr = SecretStr("")  # API-Key für Weaviate-Authentifizierung (WEAVIATE_API_KEY)
    weaviate_indexing_enabled: bool = False

    @field_validator("weaviate_indexing_enabled", mode="before")
    @classmethod
    def parse_weaviate_indexing_enabled(cls, v: str | bool) -> bool:
        if isinstance(v, bool):
            return v
        s = str(v).strip().lower()
        return s in ("true", "1", "yes", "on")
    weaviate_chunk_size_chars: int = 800
    weaviate_chunk_overlap_chars: int = 100
    weaviate_top_k: int = 5
    weaviate_legal_bases_top_k: int = 8
    ollama_embedding_model: str = "nomic-embed-text"

    @model_validator(mode="after")
    def validate_storage_and_oidc(self) -> "Settings":
        """Fail fast at startup when required settings are missing for selected backends."""
        import logging as _logging
        _log = _logging.getLogger("app.startup")

        def _redact_url(url: str) -> str:
            """Return a safe-to-log URL without userinfo (password)."""
            try:
                p = urllib.parse.urlparse(url)
                netloc = p.netloc
                if "@" in netloc:
                    netloc = f"***@{netloc.split('@', 1)[1]}"
                return urllib.parse.urlunparse((p.scheme, netloc, p.path, p.params, p.query, p.fragment))
            except Exception:
                return "<unparseable>"

        # F5: DATABASE_URL must always be set explicitly — no default credentials.
        if not self.database_url:
            raise ValueError(
                "DATABASE_URL must be set. Example: "
                "postgresql+asyncpg://user:password@host:5432/dbname"
            )

        # Celery broker URL: validate early with a helpful error message.
        # Avoid logging secrets by redacting userinfo.
        broker_url = (self.celery_broker_url or "").strip()
        if self.celery_enabled and broker_url:
            try:
                p = urllib.parse.urlparse(broker_url)
                if p.scheme not in ("redis", "rediss", "amqp", "pyamqp"):
                    raise ValueError(f"unsupported scheme {p.scheme!r}")
                if not p.hostname:
                    raise ValueError("missing hostname")
                # Accessing .port can raise ValueError if it is not an int.
                _ = p.port  # noqa: F841
            except Exception as exc:
                safe = _redact_url(broker_url)
                raise ValueError(
                    "CELERY_BROKER_URL ist ungültig und kann nicht geparst werden. "
                    "Erwartetes Format (Redis): redis://:PASSWORD@HOST:6379/0 "
                    "(Passwort ggf. URL-encoden oder ein hex-Passwort verwenden). "
                    f"Aktuell (redacted): {safe}. Fehler: {exc}"
                ) from exc

        # LLM timeout: check_timeout_seconds must be >= ollama_timeout_seconds
        # so that the asyncio.wait_for wrapper around the HTTP call does not
        # cancel the request before the HTTP client returns its own timeout error.
        # Exception: 0 means "disabled" for either knob.
        if (
            self.llm_provider == "ollama"
            and self.check_timeout_seconds > 0
            and self.ollama_timeout_seconds > 0
            and self.check_timeout_seconds < self.ollama_timeout_seconds
        ):
            raise ValueError(
                f"CHECK_TIMEOUT_SECONDS ({self.check_timeout_seconds:.1f}s) must be "
                f">= OLLAMA_TIMEOUT_SECONDS ({self.ollama_timeout_seconds:.1f}s). "
                "Checks would be cancelled before the HTTP client can surface its own "
                "timeout error. Increase CHECK_TIMEOUT_SECONDS or decrease OLLAMA_TIMEOUT_SECONDS."
            )

        if self.storage_backend == "minio":
            missing = [f for f in ("s3_endpoint_url", "s3_access_key", "s3_secret_key") if not getattr(self, f)]
            if missing:
                raise ValueError(
                    f"storage_backend=minio requires these env vars to be set: {', '.join(m.upper() for m in missing)}"
                )
        # Production-profile enforcement is handled further down, gated by
        # APP_ENVIRONMENT. The older check that used DEBUG as a proxy for
        # production was removed because it fired in test environments whenever
        # DEBUG defaulted to false.

        if self.oidc_enabled:
            if not self.oidc_issuer_url:
                raise ValueError("OIDC_ENABLED=true requires OIDC_ISSUER_URL to be set")
            if not self.oidc_client_id:
                raise ValueError("OIDC_ENABLED=true requires OIDC_CLIENT_ID to be set")
            # F2: OIDC_AUDIENCE must be set to prevent cross-application token reuse.
            if not self.oidc_audience:
                raise ValueError(
                    "SECURITY: OIDC_ENABLED=true requires OIDC_AUDIENCE to be set. "
                    "Set it to the expected JWT audience claim (typically the client ID) "
                    "to prevent tokens issued for other applications from being accepted."
                )

        # F4: In production with OIDC, webhook secrets must be encrypted at rest.
        if not self.webhook_secret_encryption_key.get_secret_value():
            if self.oidc_enabled:
                raise ValueError(
                    "SECURITY: WEBHOOK_SECRET_ENCRYPTION_KEY must be set when OIDC is enabled. "
                    "Generate a key with: "
                    "python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
                )
            _log.warning(
                "SECURITY: WEBHOOK_SECRET_ENCRYPTION_KEY not set — webhook secrets are stored "
                "unencrypted in the database. Generate a key with: "
                "python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
            )

        if not self.debug:
            origins = self.cors_origins if isinstance(self.cors_origins, list) else []
            http_origins = [o for o in origins if o.startswith("http://")]
            if http_origins:
                _log.warning(
                    "SECURITY: CORS_ORIGINS contains non-HTTPS origins in non-debug mode: %s. "
                    "Use HTTPS-only origins in production.",
                    http_origins,
                )

        # Production profile: turn the earlier advisory warnings into hard
        # failures so that a misconfigured deployment never boots. Development
        # and test environments keep their lenient behaviour.
        if self.app_environment == "production":
            problems: list[str] = []
            if not self.oidc_enabled:
                problems.append("OIDC_ENABLED must be true")
            if self.debug:
                problems.append("DEBUG must be false")
            if not self.webhook_secret_encryption_key.get_secret_value():
                problems.append("WEBHOOK_SECRET_ENCRYPTION_KEY must be set")
            origins = self.cors_origins if isinstance(self.cors_origins, list) else []
            http_origins = [o for o in origins if o.startswith("http://")]
            if http_origins:
                problems.append(
                    f"CORS_ORIGINS must use HTTPS only (rejected: {http_origins})"
                )
            trusted = self.trusted_proxies if isinstance(self.trusted_proxies, list) else []
            if not trusted:
                _log.warning(
                    "SECURITY: APP_ENVIRONMENT=production but TRUSTED_PROXIES is empty. "
                    "Set it to the CIDR range of your load balancer so X-Forwarded-For "
                    "is honoured; otherwise rate limits apply to the LB IP as one source."
                )
            if problems:
                raise ValueError(
                    "SECURITY: APP_ENVIRONMENT=production requires: "
                    + "; ".join(problems)
                )

        return self

    @property
    def database_sync_url(self) -> str:
        """Sync DB URL for Celery worker (psycopg2)."""
        return self.database_url.replace("postgresql+asyncpg", "postgresql+psycopg2", 1)



settings = Settings()
