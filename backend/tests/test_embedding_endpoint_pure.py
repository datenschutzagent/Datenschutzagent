"""Unit tests for the OpenAI-compatible embedding path in weaviate_service (no network)."""
from pydantic import SecretStr

from app.config import settings
from app.services import weaviate_service as ws


class _FakeEmbedResp:
    def __init__(self, vector):
        self._vector = vector

    def raise_for_status(self):
        return None

    def json(self):
        return {"data": [{"embedding": self._vector, "index": 0}], "model": "x"}


def test_endpoint_none_when_unconfigured(monkeypatch):
    monkeypatch.setattr(settings, "embedding_base_url", "", raising=False)
    assert ws._openai_embedding_endpoint() is None


def test_endpoint_appends_v1_and_auth_header(monkeypatch):
    monkeypatch.setattr(settings, "embedding_base_url", "http://tei:8081", raising=False)
    monkeypatch.setattr(settings, "embedding_api_key", SecretStr("k"), raising=False)
    url, headers = ws._openai_embedding_endpoint()
    assert url == "http://tei:8081/v1/embeddings"
    assert headers == {"Authorization": "Bearer k"}


def test_endpoint_keeps_existing_v1(monkeypatch):
    monkeypatch.setattr(settings, "embedding_base_url", "http://vllm:8000/v1/", raising=False)
    monkeypatch.setattr(settings, "embedding_api_key", SecretStr(""), raising=False)
    url, headers = ws._openai_embedding_endpoint()
    assert url == "http://vllm:8000/v1/embeddings"
    assert headers == {}


def test_embedding_model_falls_back_to_legacy_setting(monkeypatch):
    monkeypatch.setattr(settings, "embedding_model", "", raising=False)
    monkeypatch.setattr(settings, "ollama_embedding_model", "nomic-embed-text", raising=False)
    assert ws._embedding_model_name() == "nomic-embed-text"
    monkeypatch.setattr(settings, "embedding_model", "BAAI/bge-m3", raising=False)
    assert ws._embedding_model_name() == "BAAI/bge-m3"


def test_get_embedding_uses_openai_endpoint_when_configured(monkeypatch):
    import httpx

    monkeypatch.setattr(settings, "embedding_base_url", "http://vllm:8000", raising=False)
    monkeypatch.setattr(settings, "embedding_api_key", SecretStr(""), raising=False)
    monkeypatch.setattr(settings, "embedding_model", "BAAI/bge-m3", raising=False)
    captured = {}

    def _capture(url, json=None, headers=None, timeout=None):
        captured["url"] = url
        captured["payload"] = json
        return _FakeEmbedResp([0.1, 0.2, 0.3])

    monkeypatch.setattr(httpx, "post", _capture)
    vector = ws.get_embedding("Verzeichnis der Verarbeitungstätigkeiten")
    assert vector == [0.1, 0.2, 0.3]
    assert captured["url"] == "http://vllm:8000/v1/embeddings"
    assert captured["payload"]["model"] == "BAAI/bge-m3"


def test_get_embedding_openai_endpoint_failure_returns_empty(monkeypatch):
    import httpx

    monkeypatch.setattr(settings, "embedding_base_url", "http://vllm:8000", raising=False)

    def _boom(*a, **k):
        raise RuntimeError("connection refused")

    monkeypatch.setattr(httpx, "post", _boom)
    assert ws.get_embedding("text") == []
