"""Pure unit tests for the Weaviate hybrid-search helper (no Weaviate server)."""
from app.config import settings
from app.services.weaviate_service import _query_collection


class _FakeQuery:
    def __init__(self, hybrid_error: Exception | None = None):
        self.hybrid_calls: list[dict] = []
        self.near_vector_calls: list[dict] = []
        self._hybrid_error = hybrid_error

    def hybrid(self, **kwargs):
        self.hybrid_calls.append(kwargs)
        if self._hybrid_error is not None:
            raise self._hybrid_error
        return "hybrid-response"

    def near_vector(self, **kwargs):
        self.near_vector_calls.append(kwargs)
        return "vector-response"


class _FakeCollection:
    def __init__(self, hybrid_error: Exception | None = None):
        self.query = _FakeQuery(hybrid_error)


_VECTOR = [0.1, 0.2, 0.3]


def test_hybrid_called_with_query_vector_alpha(monkeypatch):
    monkeypatch.setattr(settings, "weaviate_hybrid_enabled", True, raising=False)
    monkeypatch.setattr(settings, "weaviate_hybrid_alpha", 0.5, raising=False)
    col = _FakeCollection()
    resp = _query_collection(col, "Speicherdauer Art. 28", _VECTOR, limit=5, filters="F")
    assert resp == "hybrid-response"
    assert col.query.near_vector_calls == []
    (call,) = col.query.hybrid_calls
    assert call == {
        "query": "Speicherdauer Art. 28",
        "vector": _VECTOR,
        "alpha": 0.5,
        "limit": 5,
        "filters": "F",
    }


def test_hybrid_failure_falls_back_to_near_vector(monkeypatch):
    monkeypatch.setattr(settings, "weaviate_hybrid_enabled", True, raising=False)
    col = _FakeCollection(hybrid_error=RuntimeError("hybrid not supported"))
    resp = _query_collection(col, "Anforderung", _VECTOR, limit=7, filters="F")
    assert resp == "vector-response"
    assert len(col.query.hybrid_calls) == 1
    (call,) = col.query.near_vector_calls
    assert call == {"near_vector": _VECTOR, "limit": 7, "filters": "F"}


def test_hybrid_disabled_uses_near_vector_directly(monkeypatch):
    monkeypatch.setattr(settings, "weaviate_hybrid_enabled", False, raising=False)
    col = _FakeCollection()
    resp = _query_collection(col, "Anforderung", _VECTOR, limit=3, filters=None)
    assert resp == "vector-response"
    assert col.query.hybrid_calls == []
    (call,) = col.query.near_vector_calls
    assert call == {"near_vector": _VECTOR, "limit": 3, "filters": None}
