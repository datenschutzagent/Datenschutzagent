"""Application configuration."""
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

    # API
    api_v1_prefix: str = "/api/v1"

    # Database
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/datenschutzagent"

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

    # CORS (in .env als kommagetrennte Liste, z. B. CORS_ORIGINS=http://localhost:3000,http://localhost:5173)
    cors_origins: str | list[str] = ["http://localhost:3002", "http://127.0.0.1:3002", "http://localhost:5173", "http://127.0.0.1:5173"]

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: str | list[str]) -> list[str]:
        if isinstance(v, list):
            return v
        return [x.strip() for x in str(v).split(",") if x.strip()]

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
    weaviate_api_key: str = ""  # API-Key für Weaviate-Authentifizierung (WEAVIATE_API_KEY)
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
            _log.warning(
                "LLM timeout misconfiguration: CHECK_TIMEOUT_SECONDS (%.1fs) < "
                "OLLAMA_TIMEOUT_SECONDS (%.1fs). Checks may be cancelled before "
                "the HTTP client can surface its own timeout. Set CHECK_TIMEOUT_SECONDS "
                ">= OLLAMA_TIMEOUT_SECONDS.",
                self.check_timeout_seconds,
                self.ollama_timeout_seconds,
            )

        if self.storage_backend == "minio":
            missing = [f for f in ("s3_endpoint_url", "s3_access_key", "s3_secret_key") if not getattr(self, f)]
            if missing:
                raise ValueError(
                    f"storage_backend=minio requires these env vars to be set: {', '.join(m.upper() for m in missing)}"
                )
        if self.oidc_enabled:
            if not self.oidc_issuer_url:
                raise ValueError("OIDC_ENABLED=true requires OIDC_ISSUER_URL to be set")
            if not self.oidc_client_id:
                raise ValueError("OIDC_ENABLED=true requires OIDC_CLIENT_ID to be set")
            if not self.oidc_audience:
                _log.warning(
                    "SECURITY: OIDC_AUDIENCE not set — JWT audience claim will NOT be verified. "
                    "Set OIDC_AUDIENCE to the expected client ID for stricter token validation."
                )

        if not self.webhook_secret_encryption_key.get_secret_value():
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

        return self

    @property
    def database_sync_url(self) -> str:
        """Sync DB URL for Celery worker (psycopg2)."""
        return self.database_url.replace("postgresql+asyncpg", "postgresql+psycopg2", 1)



settings = Settings()
