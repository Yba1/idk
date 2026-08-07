"""Pure condition-similarity scoring helpers, no embedding model.

v1 computed its own embeddings locally with sentence-transformers. v2 moves
embedding into Snowflake (SNOWFLAKE.CORTEX.EMBED_TEXT_768 +
VECTOR_COSINE_SIMILARITY over CONDITIONS.CONDITION_VEC, see
backend/snowflake/retrieval.py:closest_conditions). This module keeps only
the model-free scoring/threshold logic that both the live retriever and
FakeRetrieval-style callers can share.
"""
from __future__ import annotations

import math
from typing import Sequence

# Derived threshold from gold-set queries + out-of-scope probes. In-scope
# queries (movement disorders, dementia variants, CNS inflammation) have
# top-condition similarity >= this value; out-of-scope queries (liver
# cancer, COVID lung CT, etc.) fall below it. Kept byte-identical to v1's
# empirically-picked value.
NO_MATCH_THRESHOLD = 0.42


def cosine_similarity(a: Sequence[float], b: Sequence[float]) -> float:
    """Pure cosine similarity between two equal-length vectors. Used to
    unit-test the same math Snowflake's VECTOR_COSINE_SIMILARITY performs,
    without needing a live connection.
    """
    if len(a) != len(b) or not a:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


def is_in_scope(top_similarity: float, threshold: float = NO_MATCH_THRESHOLD) -> bool:
    """True if the closest condition's similarity clears the no-match bar."""
    return top_similarity >= threshold


def rank_condition_scores(scores: dict[str, float], top_n: int = 3) -> list[tuple[str, float]]:
    """Sort a {condition_name: similarity} map descending, stable on name."""
    return sorted(scores.items(), key=lambda kv: (kv[1], kv[0]), reverse=True)[:top_n]
