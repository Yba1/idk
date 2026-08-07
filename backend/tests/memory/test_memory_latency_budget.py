"""Memory reads get a hard 300ms combined budget; a slow backend must not be
allowed to visibly slow the demo. Personalization is worth having, not worth
a multi-second /query.
"""
import time

from fastapi.testclient import TestClient

from backend.api.main import app
from backend.contracts.fakes import FakeLedger, FakeLLM, FakeRetrieval
from backend.contracts.models import ResearcherProfile
from backend.contracts.registry import Services

client = TestClient(app)

BACKEND_SLEEP_SECONDS = 2.0


class _SlowMemory:
    def get_profile(self, user_id):
        time.sleep(BACKEND_SLEEP_SECONDS)
        return ResearcherProfile(user_id=user_id, specialty="should never surface")

    def get_thread(self, user_id, session_id):
        time.sleep(BACKEND_SLEEP_SECONDS)
        raise AssertionError("get_thread is not on the query hot path")

    def record_query(self, *a, **kw):
        pass

    def record_papers_shown(self, *a, **kw):
        pass

    def seen_pmids(self, user_id):
        time.sleep(BACKEND_SLEEP_SECONDS)
        return {"slow-pmid"}

    def set_specialty(self, *a, **kw):
        pass

    def forget(self, user_id):
        pass

    def health(self):
        return {"ok": True, "detail": "slow"}


def test_slow_memory_backend_degrades_within_the_latency_budget(monkeypatch):
    services = Services(retrieval=FakeRetrieval(), llm=FakeLLM(), memory=_SlowMemory(), ledger=FakeLedger())
    monkeypatch.setattr("backend.app.pipeline.get_services", lambda: services)

    start = time.monotonic()
    response = client.post("/query", json={
        "query": "scalp lesion uptake",
        "session_id": "s1",
        "user_id": "u1",
        "personalize": True,
    })
    elapsed = time.monotonic() - start

    assert response.status_code == 200
    body = response.json()
    assert body["memory"]["applied"] is False
    assert body["memory"]["distilled_context"] == ""
    # Bounded by the 300ms budget, not the backend's 2s sleep.
    assert elapsed < BACKEND_SLEEP_SECONDS
