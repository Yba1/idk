"""The most important test on this card: a memory backend that breaks its own
MemoryPort contract (raises on every call, instead of degrading internally)
must still never take /query down. Personalization is best-effort; search is
not.
"""
from fastapi.testclient import TestClient

from backend.api.main import app
from backend.contracts.fakes import FakeLedger, FakeLLM, FakeRetrieval
from backend.contracts.registry import Services

client = TestClient(app)


class _RaisingMemory:
    def get_profile(self, user_id):
        raise RuntimeError("EverOS down")

    def get_thread(self, user_id, session_id):
        raise RuntimeError("EverOS down")

    def record_query(self, *a, **kw):
        raise RuntimeError("EverOS down")

    def record_papers_shown(self, *a, **kw):
        raise RuntimeError("EverOS down")

    def seen_pmids(self, user_id):
        raise RuntimeError("EverOS down")

    def set_specialty(self, *a, **kw):
        raise RuntimeError("EverOS down")

    def forget(self, user_id):
        raise RuntimeError("EverOS down")

    def health(self):
        raise RuntimeError("EverOS down")


def _raising_services() -> Services:
    return Services(retrieval=FakeRetrieval(), llm=FakeLLM(), memory=_RaisingMemory(), ledger=FakeLedger())


def test_query_returns_200_with_memory_applied_false_when_backend_raises_on_every_call(monkeypatch):
    monkeypatch.setattr("backend.app.pipeline.get_services", _raising_services)

    response = client.post("/query", json={
        "query": "scalp lesion uptake",
        "session_id": "s1",
        "user_id": "u1",
        "personalize": True,
    })

    assert response.status_code == 200
    body = response.json()
    assert body["memory"]["applied"] is False
    assert body["summary_markdown"] != "" or body["papers"] == []


def test_query_returns_200_for_non_personalized_requests_even_with_a_broken_memory_backend(monkeypatch):
    monkeypatch.setattr("backend.app.pipeline.get_services", _raising_services)

    response = client.post("/query", json={
        "query": "scalp lesion uptake",
        "session_id": "s1",
        "user_id": "u1",
        "personalize": False,
    })

    assert response.status_code == 200
    assert response.json()["memory"]["applied"] is False
