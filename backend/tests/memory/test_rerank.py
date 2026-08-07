from backend.contracts.models import Paper, ResearcherProfile, ScoredPaper
from backend.memory.rerank import (
    CONDITION_AFFINITY_BOOST,
    MEMORY_MULTIPLIER_MAX,
    MEMORY_MULTIPLIER_MIN,
    SEEN_DEMOTION,
    apply_memory,
)


def _paper(pmid: str, condition: str, *, is_rare: bool = False) -> Paper:
    return Paper(
        pmid=pmid, title=f"Title {pmid}", abstract="abstract", journal="J",
        year=2020, condition=condition, is_rare=is_rare, url="https://example.com",
    )


def _scored(pmid: str, condition: str, score: float, *, is_rare: bool = False, rarity_multiplier: float = 1.0) -> ScoredPaper:
    return ScoredPaper(
        paper=_paper(pmid, condition, is_rare=is_rare),
        score=score, lexical_score=score, semantic_score=0.0,
        rarity_multiplier=rarity_multiplier,
    )


def test_seen_paper_demoted_by_0_6():
    profile = ResearcherProfile(user_id="u1", specialty=None)
    results = [_scored("1", "Condition A", 10.0)]

    reordered, demoted = apply_memory(results, profile, seen={"1"})

    assert reordered[0].memory_multiplier == SEEN_DEMOTION
    assert reordered[0].score == 10.0 * SEEN_DEMOTION
    assert demoted == 1


def test_explored_condition_boosted_by_1_15():
    profile = ResearcherProfile(user_id="u1", specialty=None, conditions_explored=["Condition A"])
    results = [_scored("1", "Condition A", 10.0)]

    reordered, demoted = apply_memory(results, profile, seen=set())

    assert reordered[0].memory_multiplier == CONDITION_AFFINITY_BOOST
    assert reordered[0].score == 10.0 * CONDITION_AFFINITY_BOOST
    assert demoted == 0


def test_combined_factor_is_capped_to_0_6_1_2_range():
    # Seen (x0.6) and explored (x1.15) combine to 0.69 - within range, asserted
    # anyway so the cap still holds once a third factor is ever added.
    profile = ResearcherProfile(user_id="u1", specialty=None, conditions_explored=["Condition A"])
    results = [_scored("1", "Condition A", 10.0)]

    reordered, _ = apply_memory(results, profile, seen={"1"})

    multiplier = reordered[0].memory_multiplier
    assert MEMORY_MULTIPLIER_MIN <= multiplier <= MEMORY_MULTIPLIER_MAX
    assert multiplier == SEEN_DEMOTION * CONDITION_AFFINITY_BOOST


def test_unseen_rare_paper_still_outranks_explored_common_paper():
    """The adversarial case: a profile that has heavily explored a common
    condition must not let personalization outrank rarity - RARE_BOOST (1.6,
    baked into `score` upstream by retrieval) exceeds the memory cap (1.2), so
    an unseen rare paper always wins on equal lexical footing.
    """
    profile = ResearcherProfile(
        user_id="u1", specialty=None,
        conditions_explored=["Common condition", "Common condition", "Common condition"],
    )
    rare = _scored("rare1", "Rare condition", score=10.0 * 1.6, is_rare=True, rarity_multiplier=1.6)
    common = _scored("common1", "Common condition", score=10.0 * 1.0, is_rare=False, rarity_multiplier=1.0)

    reordered, _ = apply_memory([common, rare], profile, seen=set())

    assert reordered[0].paper.pmid == "rare1"
    assert reordered[0].score > reordered[1].score


def test_seen_rare_paper_can_legitimately_fall_below_explored_common_paper():
    """Not a cap failure: a seen rare paper (x0.6 demotion) can fall below an
    explored-but-unseen common paper (x1.15) - the demotion is doing its job.
    """
    profile = ResearcherProfile(user_id="u1", specialty=None, conditions_explored=["Common condition"])
    seen_rare = _scored("rare1", "Rare condition", score=10.0 * 1.6, is_rare=True, rarity_multiplier=1.6)
    explored_common = _scored("common1", "Common condition", score=10.0 * 1.0, is_rare=False, rarity_multiplier=1.0)

    reordered, demoted = apply_memory([seen_rare, explored_common], profile, seen={"rare1"})

    assert demoted == 1
    assert reordered[0].paper.pmid == "common1"


def test_results_resorted_when_memory_boost_changes_relative_order():
    # Pre-rerank order is [A, B] since 9.0 > 8.0. B's condition-affinity boost
    # (x1.15 -> 9.2) should flip that order, proving apply_memory re-sorts
    # rather than just annotating in place.
    profile = ResearcherProfile(user_id="u1", specialty=None, conditions_explored=["B"])
    paper_a = _scored("A", "A", score=9.0)
    paper_b = _scored("B", "B", score=8.0)

    reordered, _ = apply_memory([paper_a, paper_b], profile, seen=set())

    assert [sp.paper.pmid for sp in reordered] == ["B", "A"]
