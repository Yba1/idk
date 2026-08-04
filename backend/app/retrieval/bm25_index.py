from __future__ import annotations

import re

from rank_bm25 import BM25Okapi


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


class BM25Index:
    def __init__(self, papers: list[dict]) -> None:
        self.papers = papers
        # BM25Okapi divides by corpus size internally, so it can't be constructed
        # over an empty corpus - skip it and let search() short-circuit instead.
        self._bm25 = None
        if papers:
            corpus_tokens = [_tokenize(f"{p['title']} {p['abstract']}") for p in papers]
            self._bm25 = BM25Okapi(corpus_tokens)

    def search(self, query: str, top_k: int = 10) -> list[tuple[dict, float]]:
        if self._bm25 is None:
            return []
        scores = self._bm25.get_scores(_tokenize(query))
        ranked = sorted(zip(self.papers, scores), key=lambda pair: pair[1], reverse=True)
        return ranked[:top_k]
