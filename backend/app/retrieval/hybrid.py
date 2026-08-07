"""RESTORED module - adapter from the pre-freeze retriever onto RetrievalPort.

WHY THIS FILE EXISTS
--------------------
The v2 freeze deleted backend/app/retrieval/hybrid.py while five modules still
import it, so `backend.api.main` does not import and the API will not boot:

    backend/api/dependencies.py:14        backend/api/routes/query.py:27
    backend/app/loop/refine.py:15         backend/app/retrieval/demo_fixture.py:11
    backend/seed.py:24

Restoring it as an adapter over the FROZEN RetrievalPort fixes all five at once
with zero edits to any existing file.

SHAPE NOTE, and it matters - this is the part that bites:

    search()  returns list[tuple[dict, float]]  -- (paper, score) PAIRS, not dicts
    .papers   returns list[dict]                -- plain dicts

Verified against the surviving callers, which unpack the pairs positionally:

    backend/app/loop/refine.py:41            `papers = [p for p, _ in retrieved]`
    backend/app/retrieval/demo_fixture.py:27 `[p["pmid"] for p, _ in naive]`
    backend/api/routes/query.py:97           `p.get("condition") for p in retriever.papers`
    backend/api/routes/query.py:116          `top_papers[i]["condition"]`

So the papers are dicts, but search wraps each in a 2-tuple with its score.
Returning bare dicts from search() imports cleanly and then raises
`ValueError: too many values to unpack` on the first query - which is strictly
worse than not booting at all, because it fails on stage instead of at start-up.
This adapter was caught doing exactly that in a sandbox run; the pair shape
below is the fix.
"""
from __future__ import annotations

from typing import Any, Sequence

#: Keys the surviving callers read off a returned paper.
_PAPER_KEYS = ("pmid", "title", "abstract", "condition", "rarity", "year", "journal", "url")


def _paper_to_dict(paper: Any, scored: Any | None = None) -> dict:
    row = {
        "pmid": paper.pmid,
        "title": paper.title,
        "abstract": paper.abstract,
        "condition": paper.condition,
        "rarity": "rare" if paper.is_rare else "common",
        "year": paper.year,
        "journal": paper.journal,
        "url": paper.url,
    }
    if scored is not None:
        row["score"] = scored.score
        row["lexical_score"] = scored.lexical_score
        row["semantic_score"] = scored.semantic_score
        row["rarity_multiplier"] = scored.rarity_multiplier
    return row


class HybridRetriever:
    """Pre-freeze retriever surface on top of the frozen RetrievalPort.

    The `corpus` argument is accepted (dependencies.py reads corpus.json and
    passes it) but the port owns retrieval, so it is kept only to answer
    `.papers` without a second file read.
    """

    def __init__(self, corpus: Sequence[dict] | None = None) -> None:
        self._corpus = list(corpus or [])

    # -- port ---------------------------------------------------------------

    @property
    def _port(self):
        from backend.contracts.registry import get_services

        return get_services().retrieval

    # -- surface used by the surviving callers -------------------------------

    @property
    def papers(self) -> list[dict]:
        """Full corpus as dicts. query.py:97 counts conditions over this."""
        if self._corpus:
            return self._corpus
        # No corpus was handed in - ask the port for everything it will give.
        return [_paper_to_dict(sp.paper, sp) for sp in self._port.search("", top_k=10_000)]

    def search(
        self,
        query: str,
        *,
        secondary_query: str | None = None,
        top_k: int = 10,
        apply_rarity: bool = True,
        exclude_pmids: Sequence[str] = (),
    ) -> list[tuple[dict, float]]:
        """(paper_dict, score) pairs - see the SHAPE NOTE in the module docstring."""
        scored = self._port.search(
            query,
            secondary_query=secondary_query,
            top_k=top_k,
            apply_rarity=apply_rarity,
            exclude_pmids=exclude_pmids,
        )
        return [(_paper_to_dict(sp.paper, sp), sp.score) for sp in scored]

    def get_closest_conditions(self, query: str, top_n: int = 3) -> list[tuple[str, float, int]]:
        """(name, similarity, paper_count) triples - the shape query.py:62 unpacks."""
        return [
            (m.condition, m.similarity, m.paper_count)
            for m in self._port.closest_conditions(query, top_n=top_n)
        ]

    def get_by_pmids(self, pmids: Sequence[str]) -> list[dict]:
        return [_paper_to_dict(p) for p in self._port.get_by_pmids(pmids)]

    def health(self) -> dict:
        return self._port.health()
