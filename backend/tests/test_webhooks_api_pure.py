"""Reine Validierungs-Tests fuer app.api.routes.webhooks – ohne DB.

Schliesst die Test-Luecke, durch die ein NameError fuer ``Field`` (Commit e296f4b)
unentdeckt blieb: das Modul wurde nie importiert, weil keine Webhook-Tests existierten.
"""
import importlib

import pytest
from pydantic import ValidationError


def test_webhooks_module_imports_without_error():
    """Smoke-Test: das Modul muss importierbar sein, sonst startet die App nicht."""
    mod = importlib.import_module("app.api.routes.webhooks")
    assert hasattr(mod, "router")
    assert hasattr(mod, "WebhookCreate")
    assert hasattr(mod, "WebhookUpdate")


def test_webhook_create_accepts_valid_input():
    from app.api.routes.webhooks import WebhookCreate

    wh = WebhookCreate(
        name="My Webhook",
        url="https://example.com/hook",
        events=["case_status_changed"],
    )
    assert wh.name == "My Webhook"
    assert wh.events == ["case_status_changed"]
    assert wh.secret is None


def test_webhook_create_rejects_oversize_name():
    from app.api.routes.webhooks import WebhookCreate

    with pytest.raises(ValidationError):
        WebhookCreate(
            name="x" * 201,
            url="https://example.com/hook",
            events=[],
        )


def test_webhook_create_rejects_oversize_url():
    from app.api.routes.webhooks import WebhookCreate

    long_url = "https://example.com/" + ("a" * 2000)
    with pytest.raises(ValidationError):
        WebhookCreate(name="ok", url=long_url, events=[])


def test_webhook_create_rejects_oversize_secret():
    from app.api.routes.webhooks import WebhookCreate

    with pytest.raises(ValidationError):
        WebhookCreate(
            name="ok",
            url="https://example.com/hook",
            secret="s" * 501,
            events=[],
        )


def test_webhook_update_allows_all_optional_fields():
    from app.api.routes.webhooks import WebhookUpdate

    wh = WebhookUpdate()
    assert wh.name is None
    assert wh.url is None
    assert wh.secret is None
    assert wh.is_active is None


def test_webhook_update_validates_url_when_provided():
    from app.api.routes.webhooks import WebhookUpdate

    wh = WebhookUpdate(url="https://api.example.com/x")
    assert wh.url == "https://api.example.com/x"
