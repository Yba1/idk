from __future__ import annotations

from backend.app.retrieval.bm25_index import BM25Index
from backend.app.retrieval.condition_match import ConditionMatcher
from backend.app.retrieval.rarity import rarity_boost
from backend.app.retrieval.vector_index import VectorIndex


def _normalize(scores: dict[str, float]) -> dict[str, float]:
    if not scores:
        return {}
    lo, hi = min(scores.values()), max(scores.values())
    if hi == lo:
        return {k: 0.0 for k in scores}
    return {k: (v - lo) / (hi - lo) for k, v in scores.items()}


class HybridRetriever:
    def __init__(self, papers: list[dict]) -> None:
        self.papers = papers
        self._bm25 = BM25Index(papers)
        self._vector = VectorIndex(papers)
        self._condition_matcher = ConditionMatcher(papers, self._vector._embeddings)

    def get_closest_conditions(self, query: str, top_n: int = 3) -> list[tuple[str, float, int]]:
        """Get the closest matching conditions for a query.
        Returns [(condition_name, similarity, paper_count), ...]."""
        query_vec = self._vector._model.encode([query], normalize_embeddings=True)[0]
        return self._condition_matcher.closest_conditions(query_vec, top_n=top_n)

    def search(self, query: str, secondary_query: str | None = None, top_k: int = 10, apply_rarity: bool = True) -> list[tuple[dict, float]]:
        n = len(self.papers)

        # Primary query search
        bm25_results_primary = self._bm25.search(query, top_k=n)
        vector_results_primary = self._vector.search(query, top_k=n)

        bm25_scores_primary = {p["pmid"]: s for p, s in bm25_results_primary}
        vector_scores_primary = {p["pmid"]: s for p, s in vector_results_primary}
        bm25_norm_primary = _normalize(bm25_scores_primary)
        vector_norm_primary = _normalize(vector_scores_primary)

        # If secondary query provided, search with it too
        if secondary_query:
            bm25_results_secondary = self._bm25.search(secondary_query, top_k=n)
            vector_results_secondary = self._vector.search(secondary_query, top_k=n)

            bm25_scores_secondary = {p["pmid"]: s for p, s in bm25_results_secondary}
            vector_scores_secondary = {p["pmid"]: s for p, s in vector_results_secondary}
            bm25_norm_secondary = _normalize(bm25_scores_secondary)
            vector_norm_secondary = _normalize(vector_scores_secondary)

        combined: list[tuple[dict, float]] = []
        for paper in self.papers:
            pmid = paper["pmid"]

            # Compute primary query score
            primary_score = 0.5 * bm25_norm_primary.get(pmid, 0.0) + 0.5 * vector_norm_primary.get(pmid, 0.0)

            if secondary_query:
                # Compute secondary query score
                secondary_score = 0.5 * bm25_norm_secondary.get(pmid, 0.0) + 0.5 * vector_norm_secondary.get(pmid, 0.0)
                # Weighted merge: 60% primary, 40% secondary
                score = 0.6 * primary_score + 0.4 * secondary_score
            else:
                score = primary_score

            if apply_rarity:
                score *= rarity_boost(paper)
            combined.append((paper, score))

        combined.sort(key=lambda pair: pair[1], reverse=True)
        return combined[:top_k]
