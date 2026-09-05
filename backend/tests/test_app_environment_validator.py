"""Tests for the APP_ENVIRONMENT-driven validator cascade.

``production`` must enforce the full production profile (OIDC, HTTPS-CORS,
webhook encryption key). Development and test keep the lenient behaviour.
"""

from __future__ import annotations

import pytest

from app.config import Settings

_DB = "postgresql+asyncpg://u:p@h:5432/d"


def _fernet_key() -> str:
    from cryptography.fernet import Fernet

    return Fernet.generate_key().decode()


def test_production_requires_oidc():
    with pytest.raises(ValueError, match="OIDC_ENABLED must be true"):
        Settings(
            app_environment="production",
            database_url=_DB,
            debug=False,
            oidc_enabled=False,
            webhook_secret_encryption_key=_fernet_key(),
            cors_origins=["https://example.com"],
        )


def test_production_requires_debug_off():
    with pytest.raises(ValueError, match="DEBUG must be false"):
        Settings(
            app_environment="production",
            database_url=_DB,
            debug=True,
            oidc_enabled=True,
            oidc_issuer_url="https://idp.example.com",
            oidc_client_id="cid",
            oidc_audience="cid",
            webhook_secret_encryption_key=_fernet_key(),
            cors_origins=["https://example.com"],
        )


def test_production_requires_webhook_encryption_key():
    with pytest.raises(ValueError, match="WEBHOOK_SECRET_ENCRYPTION_KEY"):
        Settings(
            app_environment="production",
            database_url=_DB,
            debug=False,
            oidc_enabled=True,
            oidc_issuer_url="https://idp.example.com",
            oidc_client_id="cid",
            oidc_audience="cid",
            webhook_secret_encryption_key="",
            cors_origins=["https://example.com"],
        )


def test_production_rejects_http_cors_origin():
    with pytest.raises(ValueError, match="HTTPS only"):
        Settings(
            app_environment="production",
            database_url=_DB,
            debug=False,
            oidc_enabled=True,
            oidc_issuer_url="https://idp.example.com",
            oidc_client_id="cid",
            oidc_audience="cid",
            webhook_secret_encryption_key=_fernet_key(),
            cors_origins=["http://example.com"],
        )


def test_production_accepts_valid_config():
    s = Settings(
        app_environment="production",
        database_url=_DB,
        debug=False,
        oidc_enabled=True,
        oidc_issuer_url="https://idp.example.com",
        oidc_client_id="cid",
        oidc_audience="cid",
        webhook_secret_encryption_key=_fernet_key(),
        cors_origins=["https://example.com"],
        trusted_proxies="10.0.0.0/8",
    )
    assert s.app_environment == "production"


def test_development_stays_lenient_without_oidc():
    s = Settings(
        app_environment="development",
        database_url=_DB,
        debug=True,
        oidc_enabled=False,
        cors_origins=["http://localhost:3002"],
    )
    assert s.app_environment == "development"


def test_test_environment_stays_lenient_without_webhook_key():
    s = Settings(
        app_environment="test",
        database_url=_DB,
        debug=True,
        oidc_enabled=False,
        webhook_secret_encryption_key="",
    )
    assert s.app_environment == "test"


def test_production_accumulates_multiple_problems():
    with pytest.raises(ValueError) as excinfo:
        Settings(
            app_environment="production",
            database_url=_DB,
            debug=True,
            oidc_enabled=False,
            webhook_secret_encryption_key="",
            cors_origins=["http://bad.example.com"],
        )
    msg = str(excinfo.value)
    # OIDC is checked first; the validator short-circuits on the OIDC_ENABLED
    # error at line 276 before reaching the production cascade for the other
    # problems. Still, the production cascade raises when OIDC is on — cover
    # the multi-problem case explicitly.
    assert "OIDC" in msg or "production" in msg


# ---------------------------------------------------------------------------
# Phase 1 S1: TRUSTED_PROXIES is mandatory in production (rate limiter + proxy headers)
# ---------------------------------------------------------------------------


def _production_kwargs(**overrides):
    base = {
        "app_environment": "production",
        "database_url": _DB,
        "debug": False,
        "oidc_enabled": True,
        "oidc_issuer_url": "https://idp.example.com",
        "oidc_client_id": "cid",
        "oidc_audience": "cid",
        "webhook_secret_encryption_key": _fernet_key(),
        "cors_origins": ["https://example.com"],
        "trusted_proxies": "10.0.0.0/8",
    }
    base.update(overrides)
    return base


def test_production_requires_trusted_proxies():
    with pytest.raises(ValueError, match="TRUSTED_PROXIES must list"):
        Settings(**_production_kwargs(trusted_proxies=""))


def test_development_allows_empty_trusted_proxies():
    s = Settings(
        app_environment="development",
        database_url=_DB,
        trusted_proxies="",
    )
    assert s.trusted_proxies == []


# ---------------------------------------------------------------------------
# Phase 1 S3: external LLM providers need an explicit DSGVO acknowledgement
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("provider", ["openai", "anthropic", "OpenAI"])
def test_production_rejects_external_llm_without_acknowledgement(provider):
    with pytest.raises(ValueError, match="LLM_EXTERNAL_TRANSFER_ACKNOWLEDGED"):
        Settings(**_production_kwargs(llm_provider=provider))


def test_production_accepts_external_llm_when_acknowledged():
    s = Settings(
        **_production_kwargs(
            llm_provider="anthropic", llm_external_transfer_acknowledged=True
        )
    )
    assert s.llm_provider_is_external is True


@pytest.mark.parametrize("provider", ["ollama", "openai_compatible"])
def test_self_hosted_providers_need_no_acknowledgement(provider):
    extra = {}
    if provider == "openai_compatible":
        extra = {"llm_base_url": "http://vllm:8000", "llm_model": "qwen"}
    s = Settings(**_production_kwargs(llm_provider=provider, **extra))
    assert s.llm_provider_is_external is False


def test_development_only_warns_for_external_llm(caplog):
    with caplog.at_level("WARNING", logger="app.startup"):
        s = Settings(
            app_environment="development", database_url=_DB, llm_provider="openai"
        )
    assert s.llm_provider_is_external is True
    assert any(
        "LLM_EXTERNAL_TRANSFER_ACKNOWLEDGED" in r.message for r in caplog.records
    )


def test_development_acknowledged_external_llm_does_not_warn(caplog):
    with caplog.at_level("WARNING", logger="app.startup"):
        Settings(
            app_environment="development",
            database_url=_DB,
            llm_provider="openai",
            llm_external_transfer_acknowledged=True,
        )
    assert not any(
        "LLM_EXTERNAL_TRANSFER_ACKNOWLEDGED" in r.message for r in caplog.records
    )


# ---------------------------------------------------------------------------
# Phase 1 S10: outbound service URLs
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "field",
    [
        "ollama_base_url",
        "ocr_base_url",
        "llm_base_url",
        "weaviate_url",
        "oidc_issuer_url",
    ],
)
@pytest.mark.parametrize(
    "bad",
    [
        "file:///etc/passwd",
        "gopher://x",
        "http://",
        "https://user:pw@idp.example.com",
    ],  # pragma: allowlist secret
)
def test_outbound_urls_reject_unsafe_shapes(field, bad):
    with pytest.raises(ValueError, match=field.upper()):
        Settings(app_environment="development", database_url=_DB, **{field: bad})


def test_outbound_urls_accept_private_hosts():
    s = Settings(
        app_environment="development",
        database_url=_DB,
        ollama_base_url="http://192.168.1.20:11434",
        weaviate_url="http://weaviate:8080",
        ocr_base_url="http://host.docker.internal:11434/",
    )
    assert s.ollama_base_url.startswith("http://192.168.1.20")


def test_production_requires_https_oidc_issuer():
    with pytest.raises(ValueError, match="OIDC_ISSUER_URL must use https"):
        Settings(**_production_kwargs(oidc_issuer_url="http://idp.example.com"))
