import json

from unittest.mock import MagicMock
from fastapi.testclient import TestClient

from backend.app.llm_client import ChatResult
from backend.api.main import app
from backend.api.dependencies import get_llm_client, get_retriever

client = TestClient(app)


def _parse_sse_events(body_text: str) -> list[dict]:
    events = []
    for frame in body_text.split("\n\n"):
        frame = frame.strip()
        if not frame.startswith("data:"):
            continue
        events.append(json.loads(frame[len("data:"):].strip()))
    return events


def test_query_stream_emits_stage_events_then_done():
    fake_client = MagicMock()
    fake_client.chat.side_effect = [
        ChatResult(content="hypothetical case text", prompt_tokens=10, completion_tokens=5, total_tokens=15),
        ChatResult(content='{"results": [{"pmid": "40902156", "relevant": true, "confidence": 0.9}, {"pmid": "40902157", "relevant": true, "confidence": 0.85}]}', prompt_tokens=10, completion_tokens=5, total_tokens=15),
        ChatResult(content='{"summary": "Findings show focal uptake [1].", "imaging_findings": null, "teaching_point": null, "differential": []}', prompt_tokens=200, completion_tokens=20, total_tokens=220),
        ChatResult(content='{"results": [{"marker": "[1]", "sentence_index": 0, "status": "supported", "reason": "Abstract confirms focal uptake."}]}', prompt_tokens=100, completion_tokens=50, total_tokens=150),
    ]

    fake_retriever = MagicMock()
    fake_retriever.search.return_value = [
        ({"pmid": "40902156", "title": "Diffuse Cutaneous Angiosarcoma", "abstract": "Focal FDG uptake.", "rarity": "rare", "condition": "Scalp angiosarcoma"}, 0.9),
        ({"pmid": "40902157", "title": "Another Angiosarcoma Case", "abstract": "Cutaneous tumor findings.", "rarity": "rare", "condition": "Scalp angiosarcoma"}, 0.85),
    ]
    fake_retriever.get_closest_conditions.return_value = []

    app.dependency_overrides[get_llm_client] = lambda: fake_client
    app.dependency_overrides[get_retriever] = lambda: fake_retriever
    try:
        response = client.post("/query/stream", json={"query": "scalp lesion uptake"})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    events = _parse_sse_events(response.text)

    stage_events = [e for e in events if e["type"] == "stage"]
    stage_names_in_order = [e["stage"] for e in stage_events]
    expected_order = [
        "hyde_expand", "retrieval", "relevance_check",
        "compress", "summarize", "citation_check",
    ]
    assert stage_names_in_order == expected_order

    done_events = [e for e in events if e["type"] == "done"]
    assert len(done_events) == 1
    result = done_events[0]["result"]
    assert "[1]" in result["summary_text"]
    assert result["low_confidence"] is False
    assert result["degraded"] is False
    assert result["citations"][0]["pmid"] == "40902156"


def test_query_stream_includes_refine_query_stage_on_low_confidence_retry():
    fake_client = MagicMock()
    fake_client.chat.side_effect = [
        ChatResult(content="hypothetical 1", prompt_tokens=10, completion_tokens=5, total_tokens=15),
        ChatResult(content='{"results": [{"pmid": "1", "relevant": true, "confidence": 0.2}, {"pmid": "2", "relevant": false, "confidence": 0.1}]}', prompt_tokens=10, completion_tokens=5, total_tokens=15),
        ChatResult(content="refined query", prompt_tokens=10, completion_tokens=5, total_tokens=15),
        ChatResult(content="hypothetical 2", prompt_tokens=10, completion_tokens=5, total_tokens=15),
        ChatResult(content='{"results": [{"pmid": "1", "relevant": true, "confidence": 0.3}, {"pmid": "2", "relevant": false, "confidence": 0.15}]}', prompt_tokens=10, completion_tokens=5, total_tokens=15),
        ChatResult(content='{"summary": "Best-effort summary [1].", "imaging_findings": null, "teaching_point": null, "differential": []}', prompt_tokens=200, completion_tokens=20, total_tokens=220),
        ChatResult(content='{"results": [{"marker": "[1]", "sentence_index": 0, "status": "supported", "reason": "Abstract confirms summary claim."}]}', prompt_tokens=100, completion_tokens=50, total_tokens=150),
    ]

    fake_retriever = MagicMock()
    fake_retriever.search.return_value = [
        ({"pmid": "1", "title": "Paper 1", "abstract": "abstract", "rarity": "rare", "condition": "Test condition"}, 0.5),
        ({"pmid": "2", "title": "Paper 2", "abstract": "abstract", "rarity": "common", "condition": "Other condition"}, 0.3),
    ]
    fake_retriever.get_closest_conditions.return_value = []

    app.dependency_overrides[get_llm_client] = lambda: fake_client
    app.dependency_overrides[get_retriever] = lambda: fake_retriever
    try:
        response = client.post("/query/stream", json={"query": "vague query"})
    finally:
        app.dependency_overrides.clear()

    events = _parse_sse_events(response.text)
    stage_events = [e for e in events if e["type"] == "stage"]

    refine_events = [e for e in stage_events if e["stage"] == "refine_query"]
    assert len(refine_events) == 1
    assert refine_events[0]["iteration"] == 1

    iteration_2_stages = [e["stage"] for e in stage_events if e.get("iteration") == 2]
    assert iteration_2_stages == ["hyde_expand", "retrieval", "relevance_check"]

    done_events = [e for e in events if e["type"] == "done"]
    assert len(done_events) == 1
    assert done_events[0]["result"]["low_confidence"] is True
