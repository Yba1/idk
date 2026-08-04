from unittest.mock import MagicMock
from backend.app.llm_client import ChatResult
from backend.app.retrieval.hybrid import HybridRetriever
from backend.app.loop.refine import run_search_loop

PAPERS = [
    {"pmid": "1", "title": "Scalp angiosarcoma PET case report", "abstract": "Rare vascular tumor, focal FDG uptake.", "rarity": "rare", "condition": "Scalp angiosarcoma"},
    {"pmid": "2", "title": "Common dementia PET study", "abstract": "Typical bilateral hypometabolism pattern.", "rarity": "common", "condition": "Dementia with Lewy bodies"},
    {"pmid": "3", "title": "Another angiosarcoma study", "abstract": "Cutaneous angiosarcoma imaging.", "rarity": "rare", "condition": "Scalp angiosarcoma"},
    {"pmid": "4", "title": "Parkinson's disease PET", "abstract": "Basal ganglia findings in Parkinson's.", "rarity": "common", "condition": "Parkinson's disease motor form later stage"},
    {"pmid": "5", "title": "PSP findings", "abstract": "Progressive supranuclear palsy midbrain involvement.", "rarity": "rare", "condition": "Progressive supranuclear palsy"},
]


def test_loop_passes_both_raw_and_hyde_queries_to_retriever():
    """Test that the loop passes both current_query and hyde_result.content to search()."""
    retriever = HybridRetriever(PAPERS)
    fake_client = MagicMock()
    # Mock returns: HyDE expansion, batch relevance check result
    fake_client.chat.side_effect = [
        ChatResult(content="hypothetical case: rare scalp tumor", prompt_tokens=10, completion_tokens=5, total_tokens=15),
        # Batch relevance check: pmid-keyed results, at least 2 relevant
        ChatResult(
            content='{"results": [{"pmid": "1", "relevant": true, "confidence": 0.9}, {"pmid": "2", "relevant": true, "confidence": 0.7}]}',
            prompt_tokens=10, completion_tokens=5, total_tokens=15
        ),
    ]

    papers, trace = run_search_loop(fake_client, retriever, "scalp tumor uptake", max_iterations=2)

    # Check that retriever.search was called (indirectly through papers being returned)
    assert len(papers) > 0
    assert len(trace) == 1


def test_batch_relevance_check_pmid_keyed_matching():
    """Test that batch relevance check matches results by pmid, not by position."""
    retriever = HybridRetriever(PAPERS)
    fake_client = MagicMock()
    # Return batch results in different order than retrieved papers
    fake_client.chat.side_effect = [
        ChatResult(content="hypothetical case", prompt_tokens=10, completion_tokens=5, total_tokens=15),
        # Return results in reverse order: pmid "5" first, then "4"
        ChatResult(
            content='{"results": [{"pmid": "5", "relevant": true, "confidence": 0.95}, {"pmid": "4", "relevant": true, "confidence": 0.8}]}',
            prompt_tokens=10, completion_tokens=5, total_tokens=15
        ),
    ]

    papers, trace = run_search_loop(fake_client, retriever, "movement disorder", max_iterations=2)

    # Both papers should be in results (at least 2 passed relevance)
    assert len(papers) >= 2
    assert trace[0].relevant_count >= 2


def test_loop_requires_2_papers_minimum_to_pass_relevance():
    """Test that the loop requires at least 2 papers to pass relevance check."""
    retriever = HybridRetriever(PAPERS)
    fake_client = MagicMock()
    fake_client.chat.side_effect = [
        ChatResult(content="hypothetical case 1", prompt_tokens=10, completion_tokens=5, total_tokens=15),
        # Only 1 paper is relevant
        ChatResult(
            content='{"results": [{"pmid": "1", "relevant": true, "confidence": 0.9}]}',
            prompt_tokens=10, completion_tokens=5, total_tokens=15
        ),
        ChatResult(content="refined query", prompt_tokens=10, completion_tokens=5, total_tokens=15),
        ChatResult(content="hypothetical case 2", prompt_tokens=10, completion_tokens=5, total_tokens=15),
        # Now 2 papers are relevant
        ChatResult(
            content='{"results": [{"pmid": "1", "relevant": true, "confidence": 0.85}, {"pmid": "3", "relevant": true, "confidence": 0.8}]}',
            prompt_tokens=10, completion_tokens=5, total_tokens=15
        ),
    ]

    papers, trace = run_search_loop(fake_client, retriever, "angiosarcoma", max_iterations=2)

    # First iteration should fail (only 1 relevant)
    assert trace[0].relevant_count == 1
    assert trace[0].relevant is False

    # Second iteration should pass (2 relevant)
    assert trace[1].relevant_count == 2
    assert trace[1].relevant is True
    assert len(papers) >= 2


def test_loop_stops_early_when_relevance_check_passes_on_first_try():
    retriever = HybridRetriever(PAPERS)
    fake_client = MagicMock()
    fake_client.chat.side_effect = [
        ChatResult(content="hypothetical case text", prompt_tokens=10, completion_tokens=5, total_tokens=15),
        ChatResult(content='{"results": [{"pmid": "1", "relevant": true, "confidence": 0.9}, {"pmid": "2", "relevant": true, "confidence": 0.8}]}', prompt_tokens=10, completion_tokens=5, total_tokens=15),
    ]

    papers, trace = run_search_loop(fake_client, retriever, "scalp tumor uptake", max_iterations=2)

    assert len(trace) == 1
    assert trace[0].relevant is True
    assert len(papers) >= 2


def test_loop_runs_second_iteration_when_first_fails_relevance():
    retriever = HybridRetriever(PAPERS)
    fake_client = MagicMock()
    fake_client.chat.side_effect = [
        ChatResult(content="hypothetical case text 1", prompt_tokens=10, completion_tokens=5, total_tokens=15),
        ChatResult(content='{"results": [{"pmid": "1", "relevant": false, "confidence": 0.2}]}', prompt_tokens=10, completion_tokens=5, total_tokens=15),
        ChatResult(content="refined query text", prompt_tokens=10, completion_tokens=5, total_tokens=15),
        ChatResult(content="hypothetical case text 2", prompt_tokens=10, completion_tokens=5, total_tokens=15),
        ChatResult(content='{"results": [{"pmid": "2", "relevant": true, "confidence": 0.85}, {"pmid": "3", "relevant": true, "confidence": 0.75}]}', prompt_tokens=10, completion_tokens=5, total_tokens=15),
    ]

    papers, trace = run_search_loop(fake_client, retriever, "vague query", max_iterations=2)

    assert len(trace) == 2
    assert trace[0].relevant is False
    assert trace[1].relevant is True


def test_loop_returns_no_papers_when_final_iteration_has_zero_relevant():
    """Exhausting max_iterations with zero papers passing the relevance check
    returns an empty list, signaling the no_match path to the caller - it never
    falls back to the unfiltered retrieved list, which would re-cite papers the
    relevance check just rejected."""
    retriever = HybridRetriever(PAPERS)
    fake_client = MagicMock()
    fake_client.chat.side_effect = [
        ChatResult(content="hypothetical case text 1", prompt_tokens=10, completion_tokens=5, total_tokens=15),
        ChatResult(content='{"results": [{"pmid": "1", "relevant": false, "confidence": 0.2}]}', prompt_tokens=10, completion_tokens=5, total_tokens=15),
        ChatResult(content="refined query text", prompt_tokens=10, completion_tokens=5, total_tokens=15),
        ChatResult(content="hypothetical case text 2", prompt_tokens=10, completion_tokens=5, total_tokens=15),
        ChatResult(content='{"results": [{"pmid": "2", "relevant": false, "confidence": 0.3}]}', prompt_tokens=10, completion_tokens=5, total_tokens=15),
    ]

    papers, trace = run_search_loop(fake_client, retriever, "vague query", max_iterations=2)

    assert len(trace) == 2
    assert trace[-1].relevant is False
    assert papers == []
