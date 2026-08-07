"""/query/stream emits `stage` events as the search loop progresses, using
the same stage names v1 used - frontend/src/components/progress-timeline.tsx
(Card 2B's) already renders against exactly this set, so matching it here
means that component works without Codex having to change anything.
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


def test_query_stream_emits_stage_events_then_done(monkeypatch):
    monkeypatch.setenv("NEULIT_PROFILE", "fake")
    get_services.cache_clear()

    response = client.post("/query/stream", json={
        "query": DEMO_QUERY, "session_id": "s1", "user_id": "u1", "personalize": True,
    })

    assert response.status_code == 200
    events = _parse_sse_events(response.text)

    stage_names = [e["stage"] for e in events if e["type"] == "stage"]
    # FakeLLM's canned relevance_check always passes, so this is a single,
    # non-refining round: exactly these five stages, in order, once each.
    assert stage_names == ["hyde_expand", "retrieval", "relevance_check", "summarize", "citation_check"]

    done_events = [e for e in events if e["type"] == "done"]
    assert len(done_events) == 1
    result = done_events[0]["result"]
    assert result["request_id"]
    assert len(result["papers"]) > 0


def test_query_stream_stage_events_carry_iteration_number(monkeypatch):
    monkeypatch.setenv("NEULIT_PROFILE", "fake")
    get_services.cache_clear()

    response = client.post("/query/stream", json={
        "query": DEMO_QUERY, "session_id": "s1", "user_id": "u1", "personalize": False,
    })

    stage_events = [e for e in _parse_sse_events(response.text) if e["type"] == "stage"]
    loop_stages = [e for e in stage_events if e["stage"] in ("hyde_expand", "retrieval", "relevance_check")]
    assert all(e.get("iteration") == 1 for e in loop_stages)
