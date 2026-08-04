"""Out-of-scope query detection via condition-centroid similarity.

Computes per-condition embeddings from the paper embeddings in the corpus,
allowing us to detect when a query is genuinely outside the 14-condition scope
rather than just retrieving low-relevance results.
"""
from __future__ import annotations

import numpy as np
from sentence_transformers import SentenceTransformer

MODEL_NAME = "all-MiniLM-L6-v2"

# Derived threshold from gold-set queries + out-of-scope probes (Section 3).
# In-scope queries (movement disorders, dementia variants, CNS inflammation)
# have top-condition similarity >= this value; out-of-scope queries (liver cancer,
# COVID lung CT, etc.) fall below it. Threshold was empirically picked to separate
# the two distributions without overlap.
NO_MATCH_THRESHOLD = 0.42


class ConditionMatcher:
    def __init__(self, papers: list[dict], embeddings: np.ndarray) -> None:
        """
        Build condition centroids from paper embeddings.

        Args:
            papers: List of paper dicts, each with 'pmid' and 'condition' keys.
            embeddings: Pre-computed paper embeddings (from VectorIndex).
        """
        self.papers = papers
        self.embeddings = embeddings
        self._model = SentenceTransformer(MODEL_NAME)
        self.condition_centroids: dict[str, np.ndarray] = {}
        self.condition_paper_counts: dict[str, int] = {}

        # Group papers by condition and compute centroid
        papers_by_condition: dict[str, list[int]] = {}
        for idx, paper in enumerate(papers):
            condition = paper.get("condition", "Unknown")
            if condition not in papers_by_condition:
                papers_by_condition[condition] = []
            papers_by_condition[condition].append(idx)

        for condition, indices in papers_by_condition.items():
            condition_embeddings = embeddings[indices]
            centroid = np.mean(condition_embeddings, axis=0)
            # Normalize to unit vector for cosine similarity
            centroid_norm = np.linalg.norm(centroid)
            if centroid_norm > 0:
                centroid = centroid / centroid_norm
            self.condition_centroids[condition] = centroid
            self.condition_paper_counts[condition] = len(indices)

    def closest_conditions(self, query_embedding: np.ndarray, top_n: int = 3) -> list[tuple[str, float, int]]:
        """
        Find the closest conditions to a query embedding.

        Args:
            query_embedding: Query embedding vector (normalized).
            top_n: Number of top conditions to return.

        Returns:
            List of (condition_name, similarity_score, paper_count) tuples,
            sorted by similarity descending.
        """
        similarities = []
        for condition, centroid in self.condition_centroids.items():
            # Cosine similarity (both already normalized)
            sim = float(np.dot(query_embedding, centroid))
            paper_count = self.condition_paper_counts.get(condition, 0)
            similarities.append((condition, sim, paper_count))

        # Sort by similarity descending
        similarities.sort(key=lambda x: x[1], reverse=True)
        return similarities[:top_n]
