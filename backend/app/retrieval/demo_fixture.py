"""The fixed demo case: a query where naive lexical ranking buries a scalp
angiosarcoma paper under common Alzheimer's disease papers, and rarity
weighting visibly surfaces it. This is what makes "rare-case-weighted"
demonstrable instead of an unverifiable adjective.

v1 built this on top of HybridRetriever (BM25 + local vectors), which is
deleted in v2 (Cortex Search now owns hybrid retrieval, see
backend/snowflake/retrieval.py). This module keeps the same deterministic
token-overlap scoring FakeRetrieval already uses (backend/contracts/fakes.py)
so the demo fixture works identically under the `fake` profile and needs no
Snowflake connection to compute.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from backend.app.retrieval.rarity import rarity_boost

CORPUS_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "corpus.json"
DEMO_QUERY = "localized hypermetabolic uptake pattern on brain imaging"

_WORD_RE = re.compile(r"[a-z0-9]+")


def _tokenize(text: str) -> set[str]:
    return set(_WORD_RE.findall(text.lower()))


def _score(query_tokens: set[str], paper: dict, apply_rarity: bool) -> float:
    paper_tokens = _tokenize(paper.get("title", "")) | _tokenize(paper.get("abstract", ""))
    lexical_score = float(len(query_tokens & paper_tokens))
    if not apply_rarity:
        return lexical_score
    return lexical_score * rarity_boost(paper)


def _search(corpus: list[dict], query: str, top_k: int, apply_rarity: bool) -> list[dict]:
    query_tokens = _tokenize(query)
    scored = [(p, _score(query_tokens, p, apply_rarity)) for p in corpus]
    scored.sort(key=lambda ps: (ps[1], ps[0]["pmid"]), reverse=True)
    return [p for p, _ in scored[:top_k]]


def run_demo_contrast() -> dict:
    corpus = json.loads(CORPUS_PATH.read_text())

    naive = _search(corpus, DEMO_QUERY, top_k=5, apply_rarity=False)
    weighted = _search(corpus, DEMO_QUERY, top_k=5, apply_rarity=True)

    rare_case = next(p for p in corpus if p["condition"] == "Scalp angiosarcoma")

    return {
        "naive_top5": [p["pmid"] for p in naive],
        "weighted_top5": [p["pmid"] for p in weighted],
        "rare_case_pmid": rare_case["pmid"],
    }
