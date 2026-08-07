"""Memory-conditioned re-rank applied on top of RetrievalPort.search results.
Pure function, no I/O: seen papers get a second-chance demotion (hard
exclusion already happened upstream via exclude_pmids), explored-condition
papers get a continuity boost, and the combined factor is capped so
personalization can never outrank the rarity boost that is this product's
core claim.
"""
from __future__ import annotations

from dataclasses import replace

from backend.contracts.models import ResearcherProfile, ScoredPaper

SEEN_DEMOTION = 0.6
CONDITION_AFFINITY_BOOST = 1.15
MEMORY_MULTIPLIER_MIN = 0.6
MEMORY_MULTIPLIER_MAX = 1.2


def apply_memory(
    results: list[ScoredPaper],
    profile: ResearcherProfile,
    seen: set[str],
) -> tuple[list[ScoredPaper], int]:
    """Returns (reordered results, count of seen papers demoted)."""
    explored = set(profile.conditions_explored)
    demoted = 0
    adjusted: list[ScoredPaper] = []

    for sp in results:
        multiplier = 1.0
        if sp.paper.pmid in seen:
            multiplier *= SEEN_DEMOTION
            demoted += 1
        if sp.paper.condition in explored:
            multiplier *= CONDITION_AFFINITY_BOOST
        multiplier = max(MEMORY_MULTIPLIER_MIN, min(MEMORY_MULTIPLIER_MAX, multiplier))
        adjusted.append(replace(sp, score=sp.score * multiplier, memory_multiplier=multiplier))

    adjusted.sort(key=lambda sp: (sp.score, sp.paper.pmid), reverse=True)
    return adjusted, demoted
