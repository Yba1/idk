import json
from pathlib import Path
from unittest.mock import MagicMock

from backend.app.llm_client import ChatResult
from backend.app.loop.refine import run_search_loop
from backend.app.retrieval.hybrid import HybridRetriever
from backend.app.summary.generate import generate_sourced_summary

CORPUS_PATH = Path(__file__).resolve().parent.parent / "data" / "corpus.json"


def test_full_pipeline_retrieval_to_sourced_summary():
    corpus = json.loads(CORPUS_PATH.read_text())
    retriever = HybridRetriever(corpus)

    # Perform a real search to get the actual top-5 pmids
    search_results = retriever.search("focal hypermetabolic uptake pattern", top_k=5)
    pmids_top5 = [p["pmid"] for p, _ in search_results]

    # Mark first 3 as relevant (enough to pass 2-paper floor)
    results_json = '{"results": [' + ', '.join(
        f'{{"pmid": "{pmid}", "relevant": true, "confidence": 0.88}}'
        for pmid in pmids_top5[:3]
    ) + ']}'

    fake_client = MagicMock()
    fake_client.chat.side_effect = [
        ChatResult(content="hypothetical scalp lesion case report", prompt_tokens=20, completion_tokens=10, total_tokens=30),
        # Batch relevance check: at least 2 papers relevant to pass
        ChatResult(content=results_json, prompt_tokens=20, completion_tokens=5, total_tokens=25),
        ChatResult(content='{"summary": "Findings show focal uptake [1], consistent with prior case reports [2].", "imaging_findings": null, "teaching_point": null, "differential": []}',
                   prompt_tokens=400, completion_tokens=50, total_tokens=450),
    ]

    papers, trace = run_search_loop(fake_client, retriever, "focal hypermetabolic uptake pattern")
    assert len(papers) > 0
    assert trace[-1].relevant is True

    summary = generate_sourced_summary(fake_client, "focal hypermetabolic uptake pattern", papers[:5])
    assert summary.degraded is False
    assert "[1]" in summary.text
    assert len(summary.citations) == len(papers[:5])
