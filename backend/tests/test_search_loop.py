"""The search loop itself now lives inside backend/app/pipeline.py (v1's
standalone run_search_loop was folded into the orchestrator); these tests
drive it through run_query with a stub retrieval/LLM to check the round/
refine mechanics rather than the full HTTP response shape.
"""
import json

from backend.app.pipeline import run_query
from backend.contracts.fakes import FakeMemory
from backend.contracts.models import ScoredPaper
from backend.contracts.registry import Services
from backend.tests._stub_llm import StubLLM, make_scored_paper


class _StubRetrieval:
    def __init__(self, by_query: dict[str, list[ScoredPaper]]):
        self.by_query = by_query
        self.queries_seen: list[str] = []

    def search(self, query, *, secondary_query=None, top_k=10, apply_rarity=True, exclude_pmids=()):
        self.queries_seen.append(query)
        return self.by_query.get(query, [])

    def closest_conditions(self, query, top_n=3):
        return []

    def get_by_pmids(self, pmids):
        return []

    def health(self):
        return {"ok": True, "detail": "stub"}


class _NoOpLedger:
    def record(self, event):
        pass

    def health(self):
        return {"ok": True, "detail": "stub"}


def _relevance_content(call_number: int) -> str:
    if call_number == 1:
        return json.dumps({"relevant": False, "confidence": 0.1, "note": "not enough evidence"})
    return json.dumps({"relevant": True, "confidence": 0.9, "note": "good match"})


def test_low_confidence_round_triggers_refine_and_retries(monkeypatch):
    round_1_papers = [make_scored_paper("p1")]
    round_2_papers = [make_scored_paper("p2"), make_scored_paper("p3")]
    retrieval = _StubRetrieval({"original query": round_1_papers, "refined query": round_2_papers})

    llm = StubLLM({
        "hyde": json.dumps({"expanded_query": "hyde text"}),
        "relevance_check": _relevance_content,
        "refine": json.dumps({"refined_query": "refined query"}),
        "summary": json.dumps({"summary_markdown": "Findings [1]."}),
        "citation_check": json.dumps({"results": [{"index": 1, "supported": True, "note": "ok"}]}),
    })

    services = Services(retrieval=retrieval, llm=llm, memory=FakeMemory(), ledger=_NoOpLedger())
    monkeypatch.setattr("backend.app.pipeline.get_services", lambda: services)

    stages: list[tuple[str, dict]] = []
    result = run_query(
        "original query", user_id="u1", session_id="s1", personalize=False,
        on_stage=lambda stage, detail: stages.append((stage, detail)),
    )

    assert retrieval.queries_seen == ["original query", "refined query"]
    assert [t.relevant for t in result.trace] == [False, True]
    assert len(result.trace) == 2
    assert [p.paper.pmid for p in result.papers] == ["p2", "p3"]

    assert [s for s, _ in stages] == [
        "hyde_expand", "retrieval", "relevance_check", "refine_query",
        "hyde_expand", "retrieval", "relevance_check", "summarize", "citation_check",
    ]
    assert [detail["iteration"] for stage, detail in stages if stage == "hyde_expand"] == [1, 2]


def test_relevant_first_round_stops_the_loop(monkeypatch):
    papers = [make_scored_paper("p1"), make_scored_paper("p2")]
    retrieval = _StubRetrieval({"good query": papers})

    llm = StubLLM({
        "hyde": json.dumps({"expanded_query": "hyde text"}),
        "relevance_check": json.dumps({"relevant": True, "confidence": 0.95, "note": "strong match"}),
        "summary": json.dumps({"summary_markdown": "Findings [1] [2]."}),
        "citation_check": json.dumps({"results": [
            {"index": 1, "supported": True, "note": "ok"},
            {"index": 2, "supported": True, "note": "ok"},
        ]}),
    })

    services = Services(retrieval=retrieval, llm=llm, memory=FakeMemory(), ledger=_NoOpLedger())
    monkeypatch.setattr("backend.app.pipeline.get_services", lambda: services)

    result = run_query("good query", user_id="u1", session_id="s1", personalize=False)

    assert retrieval.queries_seen == ["good query"]
    assert len(result.trace) == 1
    assert result.trace[0].relevant is True


def test_low_confidence_on_final_round_still_returns_the_last_papers(monkeypatch):
    # Both rounds fail relevance; the loop must still return round 2's papers
    # rather than nothing, so the summary has something to work with.
    round_1_papers = [make_scored_paper("p1")]
    round_2_papers = [make_scored_paper("p2")]
    retrieval = _StubRetrieval({"q": round_1_papers, "refined query": round_2_papers})

    llm = StubLLM({
        "hyde": json.dumps({"expanded_query": "hyde text"}),
        "relevance_check": json.dumps({"relevant": False, "confidence": 0.2, "note": "weak"}),
        "refine": json.dumps({"refined_query": "refined query"}),
        "summary": json.dumps({"summary_markdown": "Best-effort findings [1]."}),
        "citation_check": json.dumps({"results": [{"index": 1, "supported": True, "note": "ok"}]}),
    })

    services = Services(retrieval=retrieval, llm=llm, memory=FakeMemory(), ledger=_NoOpLedger())
    monkeypatch.setattr("backend.app.pipeline.get_services", lambda: services)

    result = run_query("q", user_id="u1", session_id="s1", personalize=False)

    assert len(result.trace) == 2
    assert all(t.relevant is False for t in result.trace)
    assert [p.paper.pmid for p in result.papers] == ["p2"]
