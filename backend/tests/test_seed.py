import json
from pathlib import Path
from unittest.mock import patch, MagicMock
from backend.app.llm_client import ChatResult
from backend.app.retrieval.demo_fixture import DEMO_QUERY
from backend.app.retrieval.hybrid import HybridRetriever
from backend.seed import run_seed_demo

CORPUS_PATH = Path(__file__).resolve().parent.parent / "data" / "corpus.json"


def test_run_seed_demo_returns_all_three_sections():
    # Get the actual pmids that would be returned for DEMO_QUERY
    corpus = json.loads(CORPUS_PATH.read_text())
    retriever = HybridRetriever(corpus)
    search_results = retriever.search(DEMO_QUERY, top_k=5)
    pmids_top5 = [p["pmid"] for p, _ in search_results]

    # Build batch results with actual pmids
    results_json = '{"results": [' + ', '.join(
        f'{{"pmid": "{pmid}", "relevant": true, "confidence": 0.88}}'
        for pmid in pmids_top5[:2]  # Mark first 2 as relevant
    ) + ']}'

    fake_client = MagicMock()
    fake_client.chat.side_effect = [
        ChatResult(content="hypothetical text", prompt_tokens=10, completion_tokens=5, total_tokens=15),
        # Batch relevance check: need at least 2 relevant papers
        ChatResult(content=results_json, prompt_tokens=10, completion_tokens=5, total_tokens=15),
        ChatResult(content='{"summary": "Summary with citation [1].", "imaging_findings": null, "teaching_point": null, "differential": []}', prompt_tokens=200, completion_tokens=30, total_tokens=230),
    ]

    with patch("backend.seed.ParitokLLMClient", return_value=fake_client):
        result = run_seed_demo()

    assert "demo_contrast" in result
    assert "loop_trace" in result
    assert "summary" in result
    assert result["summary"]["text"] == "Summary with citation [1]."
