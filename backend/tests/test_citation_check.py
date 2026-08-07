import json

from backend.app.summary.generate import SourcedCitation
from backend.app.verify.citation_check import check_citations
from backend.tests._stub_llm import StubLLM, make_scored_paper


def test_no_citations_short_circuits_without_a_call():
    llm = StubLLM({"citation_check": json.dumps({"results": []})})
    result = check_citations(llm, "q", "text", [], [], request_id="r1", session_id="s1", user_id="u1")
    assert result == []
    assert llm.calls == []


def test_per_claim_results_are_matched_by_index():
    papers = [make_scored_paper("p1"), make_scored_paper("p2")]
    citations = [SourcedCitation(index=1, pmid="p1"), SourcedCitation(index=2, pmid="p2")]
    llm = StubLLM({"citation_check": json.dumps({"results": [
        {"index": 1, "supported": True, "note": "confirmed"},
        {"index": 2, "supported": False, "note": "not in abstract"},
    ]})})

    result = check_citations(llm, "q", "text [1] [2]", papers, citations, request_id="r1", session_id="s1", user_id="u1")

    by_index = {c.index: c for c in result}
    assert by_index[1].supported is True
    assert by_index[1].note == "confirmed"
    assert by_index[2].supported is False


def test_flat_verdict_shape_applies_uniformly_to_all_citations():
    # Matches FakeLLM's canned {"supported": ..., "note": ...} shape (no
    # per-claim "results" list) - applied uniformly since there's nothing
    # per-claim to key off of.
    papers = [make_scored_paper("p1"), make_scored_paper("p2")]
    citations = [SourcedCitation(index=1, pmid="p1"), SourcedCitation(index=2, pmid="p2")]
    llm = StubLLM({"citation_check": json.dumps({"supported": True, "note": None})})

    result = check_citations(llm, "q", "text [1] [2]", papers, citations, request_id="r1", session_id="s1", user_id="u1")

    assert all(c.supported is True for c in result)


def test_degraded_call_leaves_citations_unverified_not_dropped():
    papers = [make_scored_paper("p1")]
    citations = [SourcedCitation(index=1, pmid="p1")]
    llm = StubLLM({}, degraded_sites={"citation_check"})

    result = check_citations(llm, "q", "text [1]", papers, citations, request_id="r1", session_id="s1", user_id="u1")

    assert len(result) == 1
    assert result[0].supported is None


def test_invalid_json_leaves_citations_unverified_not_dropped():
    papers = [make_scored_paper("p1")]
    citations = [SourcedCitation(index=1, pmid="p1")]
    llm = StubLLM({"citation_check": "not json"})

    result = check_citations(llm, "q", "text [1]", papers, citations, request_id="r1", session_id="s1", user_id="u1")

    assert len(result) == 1
    assert result[0].supported is None
