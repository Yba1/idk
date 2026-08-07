import json

from backend.app.loop.hyde import build_hyde_messages, run_hyde
from backend.app.loop.refine import run_refine
from backend.app.loop.relevance_check import run_relevance_check
from backend.tests._stub_llm import StubLLM, make_scored_paper


def test_build_hyde_messages_includes_query():
    messages = build_hyde_messages("scalp lesion uptake")
    assert any("scalp lesion uptake" in m.content for m in messages)


def test_run_hyde_returns_expanded_query_on_success():
    llm = StubLLM({"hyde": json.dumps({"expanded_query": "expanded case text"})})
    result = run_hyde(llm, "query", request_id="r1", session_id="s1", user_id="u1")
    assert result == "expanded case text"
    assert llm.calls[0][0] == "hyde"


def test_run_hyde_falls_back_to_raw_query_when_degraded():
    llm = StubLLM({}, degraded_sites={"hyde"})
    result = run_hyde(llm, "raw query", request_id="r1", session_id="s1", user_id="u1")
    assert result == "raw query"


def test_run_hyde_falls_back_on_invalid_json():
    llm = StubLLM({"hyde": "not json"})
    result = run_hyde(llm, "raw query", request_id="r1", session_id="s1", user_id="u1")
    assert result == "raw query"


def test_run_relevance_check_parses_verdict():
    papers = [make_scored_paper("1")]
    llm = StubLLM({"relevance_check": json.dumps({"relevant": True, "confidence": 0.9, "note": "ok"})})
    verdict = run_relevance_check(llm, "query", papers, request_id="r1", session_id="s1", user_id="u1")
    assert verdict == {"relevant": True, "confidence": 0.9, "note": "ok"}


def test_run_relevance_check_empty_papers_short_circuits_without_a_call():
    llm = StubLLM({"relevance_check": json.dumps({"relevant": True, "confidence": 0.9})})
    verdict = run_relevance_check(llm, "query", [], request_id="r1", session_id="s1", user_id="u1")
    assert verdict["relevant"] is False
    assert llm.calls == []


def test_run_relevance_check_degraded_treats_round_as_passing():
    papers = [make_scored_paper("1")]
    llm = StubLLM({}, degraded_sites={"relevance_check"})
    verdict = run_relevance_check(llm, "query", papers, request_id="r1", session_id="s1", user_id="u1")
    assert verdict["relevant"] is True


def test_run_refine_returns_refined_query():
    llm = StubLLM({"refine": json.dumps({"refined_query": "better query"})})
    result = run_refine(llm, "original", "note", request_id="r1", session_id="s1", user_id="u1")
    assert result == "better query"


def test_run_refine_falls_back_when_degraded():
    llm = StubLLM({}, degraded_sites={"refine"})
    result = run_refine(llm, "original", "note", request_id="r1", session_id="s1", user_id="u1")
    assert result == "original"
