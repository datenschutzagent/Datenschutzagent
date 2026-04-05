"""Application configuration."""
from pydantic import field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Settings loaded from environment."""

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

    # LLM context limits (chars per document; lower = faster/cheaper, higher = more context)
    max_context_chars_per_doc: int = 15000  # single-doc full-text context window limit
    max_context_chars_rag: int = 20000       # assembled RAG context limit

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
    oidc_client_secret: str = ""  # For token introspection / backend flows; can be empty for public clients
    oidc_audience: str | None = None  # Optional; if set, JWT aud claim must match
    oidc_scopes: str = "openid profile email"  # Space-separated

    # RBAC: default role for new users (viewer, editor, admin). Existing users updated by migration.
    rbac_default_role: str = "viewer"

    # Weaviate (optional; RAG document checks)
    weaviate_url: str = "http://localhost:8080"
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

    @property
    def database_sync_url(self) -> str:
        """Sync DB URL for Celery worker (psycopg2)."""
        return self.database_url.replace("postgresql+asyncpg", "postgresql+psycopg2", 1)

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
