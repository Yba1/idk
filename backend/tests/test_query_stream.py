"""run_query has no stage-by-stage hooks in v2 (v1's on_stage instrumentation
was dropped with llm_client.py, and the frozen HTTP contract in
plan-v2/00-SHARED-CONTRACTS.md section 4 defines no stage events for this
route), so /query/stream is a thin SSE wrapper emitting one `done` event.
"""
import json

from fastapi.testclient import TestClient

from backend.api.main import app
from backend.contracts.registry import get_services

client = TestClient(app)

DEMO_QUERY = "localized hypermetabolic uptake pattern on brain imaging"


def _parse_sse_events(body_text: str) -> list[dict]:
    events = []
    for frame in body_text.split("\n\n"):
        frame = frame.strip()
        if not frame.startswith("data:"):
            continue
        events.append(json.loads(frame[len("data:"):].strip()))
    return events


def test_query_stream_emits_a_single_done_event_with_the_full_result(monkeypatch):
    monkeypatch.setenv("NEULIT_PROFILE", "fake")
    get_services.cache_clear()

    response = client.post("/query/stream", json={
        "query": DEMO_QUERY, "session_id": "s1", "user_id": "u1", "personalize": True,
    })

    assert response.status_code == 200
    events = _parse_sse_events(response.text)
    assert [e["type"] for e in events] == ["done"]
    result = events[0]["result"]
    assert result["request_id"]
    assert len(result["papers"]) > 0
