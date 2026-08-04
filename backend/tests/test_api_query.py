from unittest.mock import MagicMock
from fastapi.testclient import TestClient

from backend.app.llm_client import ChatResult
from backend.api.main import app
from backend.api.dependencies import get_llm_client, get_retriever

client = TestClient(app)


def test_query_endpoint_returns_summary_citations_and_trace():
    fake_client = MagicMock()
    fake_client.chat.side_effect = [
        ChatResult(content="hypothetical case text", prompt_tokens=10, completion_tokens=5, total_tokens=15),
        # Batch relevance check: need at least 2 relevant papers to pass
        ChatResult(content='{"results": [{"pmid": "40902156", "relevant": true, "confidence": 0.9}, {"pmid": "40902157", "relevant": true, "confidence": 0.85}]}', prompt_tokens=10, completion_tokens=5, total_tokens=15),
        ChatResult(content='{"summary": "Findings show focal uptake [1].", "imaging_findings": null, "teaching_point": null, "differential": []}', prompt_tokens=200, completion_tokens=20, total_tokens=220),
        # Citation check: judge call
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
        response = client.post("/query", json={"query": "scalp lesion uptake"})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert "[1]" in body["summary_text"]
    assert body["low_confidence"] is False
    assert body["degraded"] is False
    assert body["no_match"] is False
    assert len(body["trace"]) == 1
    assert body["trace"][0]["relevant"] is True
    assert body["citations"][0]["pmid"] == "40902156"
    assert body["citations"][0]["condition"] == "Scalp angiosarcoma"


def test_query_endpoint_sets_low_confidence_flag_when_loop_never_confirms_relevance():
    fake_client = MagicMock()
    fake_client.chat.side_effect = [
        ChatResult(content="hypothetical 1", prompt_tokens=10, completion_tokens=5, total_tokens=15),
        # First iteration: only 1 paper relevant (fails 2-paper floor)
        ChatResult(content='{"results": [{"pmid": "1", "relevant": true, "confidence": 0.2}, {"pmid": "2", "relevant": false, "confidence": 0.1}]}', prompt_tokens=10, completion_tokens=5, total_tokens=15),
        ChatResult(content="refined query", prompt_tokens=10, completion_tokens=5, total_tokens=15),
        ChatResult(content="hypothetical 2", prompt_tokens=10, completion_tokens=5, total_tokens=15),
        # Second iteration (final): still only 1 relevant
        ChatResult(content='{"results": [{"pmid": "1", "relevant": true, "confidence": 0.3}, {"pmid": "2", "relevant": false, "confidence": 0.15}]}', prompt_tokens=10, completion_tokens=5, total_tokens=15),
        ChatResult(content='{"summary": "Best-effort summary [1].", "imaging_findings": null, "teaching_point": null, "differential": []}', prompt_tokens=200, completion_tokens=20, total_tokens=220),
        # Citation check: judge call
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
        response = client.post("/query", json={"query": "vague query"})
    finally:
        app.dependency_overrides.clear()

    body = response.json()
    assert body["low_confidence"] is True
    assert body["summary_text"].startswith("Note:")
    assert body["no_match"] is False


def test_query_endpoint_shows_no_match_when_no_papers_pass_relevance():
    """Test that when no papers pass the relevance filter after both iterations,
    the response shows no_match=true."""
    fake_client = MagicMock()
    fake_client.chat.side_effect = [
        ChatResult(content="hypothetical case 1", prompt_tokens=10, completion_tokens=5, total_tokens=15),
        # Iteration 1: no papers pass relevance (need 2)
        ChatResult(content='{"results": []}', prompt_tokens=10, completion_tokens=5, total_tokens=15),
        ChatResult(content="refined query", prompt_tokens=10, completion_tokens=5, total_tokens=15),
        ChatResult(content="hypothetical case 2", prompt_tokens=10, completion_tokens=5, total_tokens=15),
        # Iteration 2 (final): still no papers pass
        ChatResult(content='{"results": []}', prompt_tokens=10, completion_tokens=5, total_tokens=15),
    ]

    fake_retriever = MagicMock()
    # Return empty papers on both searches
    fake_retriever.search.return_value = []
    # Closest conditions returns low similarity (out of scope)
    fake_retriever.get_closest_conditions.return_value = [
        ("Dementia with Lewy bodies", 0.35, 25),
    ]

    app.dependency_overrides[get_llm_client] = lambda: fake_client
    app.dependency_overrides[get_retriever] = lambda: fake_retriever
    try:
        response = client.post("/query", json={"query": "liver cancer PET scan"})
    finally:
        app.dependency_overrides.clear()

    body = response.json()
    assert body["no_match"] is True
    assert body["summary_text"] == ""
    assert body["citations"] == []


def test_query_endpoint_shows_sparsity_note_for_low_paper_count_condition():
    """Test that conditions with fewer than 10 papers show a sparsity note instead of low-confidence."""
    fake_client = MagicMock()
    fake_client.chat.side_effect = [
        ChatResult(content="hypothetical case", prompt_tokens=10, completion_tokens=5, total_tokens=15),
        # 2 papers pass relevance (from sparse condition)
        ChatResult(content='{"results": [{"pmid": "rare1", "relevant": true, "confidence": 0.8}, {"pmid": "rare2", "relevant": true, "confidence": 0.75}]}', prompt_tokens=10, completion_tokens=5, total_tokens=15),
        ChatResult(content='{"summary": "Rare condition findings [1] [2].", "imaging_findings": null, "teaching_point": null, "differential": []}', prompt_tokens=200, completion_tokens=20, total_tokens=220),
        # Citation check: judge call for both markers
        ChatResult(content='{"results": [{"marker": "[1]", "status": "supported", "reason": "First claim supported."}, {"marker": "[2]", "status": "supported", "reason": "Second claim supported."}]}', prompt_tokens=100, completion_tokens=50, total_tokens=150),
    ]

    fake_retriever = MagicMock()
    # Neurolymphomatosis has only 4 papers in corpus
    fake_retriever.search.return_value = [
        ({"pmid": "rare1", "title": "Neurolymphomatosis case 1", "abstract": "CNS involvement findings.", "rarity": "rare", "condition": "Neurolymphomatosis CNS involvement"}, 0.85),
        ({"pmid": "rare2", "title": "Neurolymphomatosis case 2", "abstract": "Leptomeningeal involvement.", "rarity": "rare", "condition": "Neurolymphomatosis CNS involvement"}, 0.80),
    ]
    fake_retriever.get_closest_conditions.return_value = []

    app.dependency_overrides[get_llm_client] = lambda: fake_client
    app.dependency_overrides[get_retriever] = lambda: fake_retriever
    try:
        response = client.post("/query", json={"query": "neurolymphomatosis CNS findings"})
    finally:
        app.dependency_overrides.clear()

    body = response.json()
    assert body["low_confidence"] is False
    assert body["no_match"] is False
    # Summary should have sparsity note (limited coverage message)
    assert "limited" in body["summary_text"].lower() or "sparse" in body["summary_text"].lower() or "Note:" in body["summary_text"]


def test_query_endpoint_corpus_paper_count_reflects_full_retriever_papers():
    """Test that corpus_paper_count is computed against retriever.papers (full corpus),
    not the relevance-filtered 5-paper subset."""
    fake_client = MagicMock()
    fake_client.chat.side_effect = [
        ChatResult(content="hypothetical case", prompt_tokens=10, completion_tokens=5, total_tokens=15),
        # Only 2 papers pass relevance
        ChatResult(content='{"results": [{"pmid": "p1", "relevant": true, "confidence": 0.9}, {"pmid": "p2", "relevant": true, "confidence": 0.85}]}', prompt_tokens=10, completion_tokens=5, total_tokens=15),
        ChatResult(content='{"summary": "Findings [1] [2].", "imaging_findings": null, "teaching_point": null, "differential": []}', prompt_tokens=200, completion_tokens=20, total_tokens=220),
        # Citation check
        ChatResult(content='{"results": [{"marker": "[1]", "status": "supported", "reason": "OK"}, {"marker": "[2]", "status": "supported", "reason": "OK"}]}', prompt_tokens=100, completion_tokens=50, total_tokens=150),
    ]

    fake_retriever = MagicMock()
    # retriever.papers has 15 papers with condition "Scalp angiosarcoma"
    fake_retriever.papers = [
        {"pmid": f"p{i}", "condition": "Scalp angiosarcoma", "title": f"Paper {i}", "abstract": "abstract"}
        for i in range(15)
    ]
    # search returns only 2 papers (subset)
    fake_retriever.search.return_value = [
        ({"pmid": "p1", "title": "Paper 1", "abstract": "abstract", "rarity": "rare", "condition": "Scalp angiosarcoma"}, 0.9),
        ({"pmid": "p2", "title": "Paper 2", "abstract": "abstract", "rarity": "rare", "condition": "Scalp angiosarcoma"}, 0.85),
    ]
    fake_retriever.get_closest_conditions.return_value = []

    app.dependency_overrides[get_llm_client] = lambda: fake_client
    app.dependency_overrides[get_retriever] = lambda: fake_retriever
    try:
        response = client.post("/query", json={"query": "scalp angiosarcoma"})
    finally:
        app.dependency_overrides.clear()

    body = response.json()
    assert body["case_context"] is not None
    # corpus_paper_count should be 15 (all papers in retriever.papers with that condition)
    assert body["case_context"]["corpus_paper_count"] == 15
    # sparse_coverage should be False since 15 >= SPARSITY_FLOOR (10)
    assert "Note:" not in body["summary_text"] or "limited" not in body["summary_text"].lower()


def test_query_endpoint_case_context_is_none_when_summary_degrades():
    """Test that case_context is None whenever the summary call degrades,
    even when the condition lookup would otherwise succeed."""
    fake_client = MagicMock()
    fake_client.chat.side_effect = [
        ChatResult(content="hypothetical case", prompt_tokens=10, completion_tokens=5, total_tokens=15),
        # 2 papers pass relevance
        ChatResult(content='{"results": [{"pmid": "p1", "relevant": true, "confidence": 0.9}, {"pmid": "p2", "relevant": true, "confidence": 0.85}]}', prompt_tokens=10, completion_tokens=5, total_tokens=15),
        # Summary call degrades
        ChatResult(content='', prompt_tokens=0, completion_tokens=0, total_tokens=0, degraded=True, error='timeout'),
    ]

    fake_retriever = MagicMock()
    fake_retriever.papers = [
        {"pmid": "p1", "condition": "Scalp angiosarcoma", "title": "Paper 1", "abstract": "abstract"},
        {"pmid": "p2", "condition": "Scalp angiosarcoma", "title": "Paper 2", "abstract": "abstract"},
    ]
    fake_retriever.search.return_value = [
        ({"pmid": "p1", "title": "Paper 1", "abstract": "abstract", "rarity": "rare", "condition": "Scalp angiosarcoma"}, 0.9),
        ({"pmid": "p2", "title": "Paper 2", "abstract": "abstract", "rarity": "rare", "condition": "Scalp angiosarcoma"}, 0.85),
    ]
    fake_retriever.get_closest_conditions.return_value = []

    app.dependency_overrides[get_llm_client] = lambda: fake_client
    app.dependency_overrides[get_retriever] = lambda: fake_retriever
    try:
        response = client.post("/query", json={"query": "scalp angiosarcoma"})
    finally:
        app.dependency_overrides.clear()

    body = response.json()
    assert body["degraded"] is True
    assert body["case_context"] is None


def test_query_endpoint_populates_case_context_with_condition_details():
    """Test that case_context is populated with correct fields from CONDITIONS lookup."""
    fake_client = MagicMock()
    fake_client.chat.side_effect = [
        ChatResult(content="hypothetical case", prompt_tokens=10, completion_tokens=5, total_tokens=15),
        ChatResult(content='{"results": [{"pmid": "p1", "relevant": true, "confidence": 0.9}, {"pmid": "p2", "relevant": true, "confidence": 0.85}]}', prompt_tokens=10, completion_tokens=5, total_tokens=15),
        ChatResult(content='{"summary": "Findings [1].", "imaging_findings": "Focal uptake", "teaching_point": "Consider angiosarcoma.", "differential": []}', prompt_tokens=200, completion_tokens=20, total_tokens=220),
        ChatResult(content='{"results": [{"marker": "[1]", "status": "supported", "reason": "OK"}]}', prompt_tokens=100, completion_tokens=50, total_tokens=150),
    ]

    fake_retriever = MagicMock()
    fake_retriever.papers = [
        {"pmid": "p1", "condition": "Scalp angiosarcoma", "title": "Paper 1", "abstract": "abstract"},
        {"pmid": "p2", "condition": "Scalp angiosarcoma", "title": "Paper 2", "abstract": "abstract"},
    ]
    fake_retriever.search.return_value = [
        ({"pmid": "p1", "title": "Paper 1", "abstract": "abstract", "rarity": "rare", "condition": "Scalp angiosarcoma"}, 0.9),
        ({"pmid": "p2", "title": "Paper 2", "abstract": "abstract", "rarity": "rare", "condition": "Scalp angiosarcoma"}, 0.85),
    ]
    fake_retriever.get_closest_conditions.return_value = []

    app.dependency_overrides[get_llm_client] = lambda: fake_client
    app.dependency_overrides[get_retriever] = lambda: fake_retriever
    try:
        response = client.post("/query", json={"query": "scalp angiosarcoma"})
    finally:
        app.dependency_overrides.clear()

    body = response.json()
    assert body["case_context"] is not None
    assert body["case_context"]["condition_name"] == "Scalp angiosarcoma"
    assert body["case_context"]["rarity"] == "rare"
    assert body["case_context"]["imaging_findings"] == "Focal uptake"
    assert body["case_context"]["teaching_point"] == "Consider angiosarcoma."
    assert body["case_context"]["corpus_paper_count"] == 2


def test_query_endpoint_self_reference_filter_blocks_differential_candidate():
    """Test that differential candidates matching the best_condition (self-reference)
    are filtered out before calling the judge."""
    from backend.api.routes.query import _is_self_reference

    # Test the _is_self_reference helper directly
    # Full name match
    assert _is_self_reference("Corticobasal syndrome", "Corticobasal syndrome") is True

    # Substring match with length ratio >= 0.5: "Corticobasal" in "Corticobasal syndrome"
    assert _is_self_reference("Corticobasal", "Corticobasal syndrome") is True

    # Substring match with length ratio < 0.5: "Acute ischemic stroke" in "Acute ischemic stroke MCA territory acute phase"
    # len("Acute ischemic stroke") = 20, len("Acute ischemic stroke MCA territory acute phase") = 46
    # 20/46 = 0.43, so should NOT match
    assert _is_self_reference("Acute ischemic stroke", "Acute ischemic stroke MCA territory acute phase") is False

    # Should not match unrelated conditions
    assert _is_self_reference("Alzheimer disease", "Scalp angiosarcoma") is False


def test_query_endpoint_differential_candidates_verified_by_judge():
    """Test that differential candidates (after self-reference filtering) are passed to check_differential."""
    fake_client = MagicMock()
    fake_client.chat.side_effect = [
        ChatResult(content="hypothetical case", prompt_tokens=10, completion_tokens=5, total_tokens=15),
        ChatResult(content='{"results": [{"pmid": "p1", "relevant": true, "confidence": 0.9}, {"pmid": "p2", "relevant": true, "confidence": 0.85}]}', prompt_tokens=10, completion_tokens=5, total_tokens=15),
        ChatResult(content='{"summary": "Findings [1].", "imaging_findings": null, "teaching_point": null, "differential": [{"condition_name": "Frontotemporal dementia", "marker": "[1]"}]}', prompt_tokens=200, completion_tokens=20, total_tokens=220),
        ChatResult(content='{"results": [{"marker": "[1]", "status": "supported", "reason": "OK"}]}', prompt_tokens=100, completion_tokens=50, total_tokens=150),
        # Differential judge call
        ChatResult(content='{"results": [{"condition_name": "Frontotemporal dementia", "marker": "[1]", "status": "supported", "reason": "Could overlap with this condition."}]}', prompt_tokens=100, completion_tokens=50, total_tokens=150),
    ]

    fake_retriever = MagicMock()
    fake_retriever.papers = [
        {"pmid": "p1", "condition": "Primary progressive aphasia semantic variant", "title": "Paper 1", "abstract": "abstract"},
        {"pmid": "p2", "condition": "Primary progressive aphasia semantic variant", "title": "Paper 2", "abstract": "abstract"},
    ]
    fake_retriever.search.return_value = [
        ({"pmid": "p1", "title": "Paper 1", "abstract": "abstract", "rarity": "rare", "condition": "Primary progressive aphasia semantic variant"}, 0.9),
        ({"pmid": "p2", "title": "Paper 2", "abstract": "abstract", "rarity": "rare", "condition": "Primary progressive aphasia semantic variant"}, 0.85),
    ]
    fake_retriever.get_closest_conditions.return_value = []

    app.dependency_overrides[get_llm_client] = lambda: fake_client
    app.dependency_overrides[get_retriever] = lambda: fake_retriever
    try:
        response = client.post("/query", json={"query": "primary progressive aphasia"})
    finally:
        app.dependency_overrides.clear()

    body = response.json()
    # The differential candidate should have been verified by the judge
    assert body["differential"] is not None
    assert len(body["differential"]) == 1
    assert body["differential"][0]["condition_name"] == "Frontotemporal dementia"
    assert body["differential"][0]["pmid"] == "p1"
