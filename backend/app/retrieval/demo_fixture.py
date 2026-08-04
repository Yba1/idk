"""The fixed demo case (plan.md Step 4.1): a query where naive BM25+vector
ranking buries a scalp angiosarcoma paper under common Alzheimer's disease
papers, and rarity weighting visibly surfaces it. This is what makes
"rare-case-weighted" demonstrable instead of an unverifiable adjective.
"""
from __future__ import annotations

import json
from pathlib import Path

from backend.app.retrieval.hybrid import HybridRetriever

CORPUS_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "corpus.json"
DEMO_QUERY = "localized hypermetabolic uptake pattern on brain imaging"


def run_demo_contrast() -> dict:
    corpus = json.loads(CORPUS_PATH.read_text())
    retriever = HybridRetriever(corpus)

    naive = retriever.search(DEMO_QUERY, top_k=5, apply_rarity=False)
    weighted = retriever.search(DEMO_QUERY, top_k=5, apply_rarity=True)

    rare_case = next(p for p in corpus if p["condition"] == "Scalp angiosarcoma")

    return {
        "naive_top5": [p["pmid"] for p, _ in naive],
        "weighted_top5": [p["pmid"] for p, _ in weighted],
        "rare_case_pmid": rare_case["pmid"],
    }
