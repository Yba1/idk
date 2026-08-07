"""Tests for the retrieval-policy dial and the A/B bench built on it.

No credentials, no network: `FakeRetrieval` + the real compressor, same as
`backend/measurement/run_policy_bench.py` itself.
"""
from __future__ import annotations

import pytest

from backend.app.llm.compress import DEFAULT_TOP_N
from backend.app.retrieval.policy import (
    DEFAULT_POLICY,
    GENEROUS,
    TIGHT,
    RetrievalPolicy,
    policy_for_label,
)


class TestRetrievalPolicy:
    def test_tight_tracks_the_compressor_default(self):
        # TIGHT must not drift from compress.py's own default.
        assert TIGHT.compress_top_n == DEFAULT_TOP_N

    def test_tight_tracks_the_pipeline_retrieval_width(self):
        from backend.app.pipeline import RETRIEVAL_TOP_K

        assert TIGHT.top_k == RETRIEVAL_TOP_K

    def test_default_policy_is_tight(self):
        assert DEFAULT_POLICY is TIGHT

    def test_generous_trades_depth_for_breadth(self):
        assert GENEROUS.top_k > TIGHT.top_k
        assert GENEROUS.compress_top_n < TIGHT.compress_top_n

    def test_generous_stays_within_tights_sentence_budget(self):
        # The whole claim is that breadth is bought, not billed for.
        assert GENEROUS.sentence_budget <= TIGHT.sentence_budget

    def test_frozen(self):
        with pytest.raises(Exception):
            TIGHT.top_k = 99  # type: ignore[misc]

    @pytest.mark.parametrize("top_k,top_n", [(0, 4), (10, 0), (-1, 4), (10, -3)])
    def test_rejects_nonsense_dials(self, top_k, top_n):
        with pytest.raises(ValueError):
            RetrievalPolicy(top_k=top_k, compress_top_n=top_n, label="bad")

    def test_policy_for_label_roundtrips(self):
        assert policy_for_label("tight") is TIGHT
        assert policy_for_label("generous") is GENEROUS

    def test_unknown_label_raises_rather_than_defaulting(self):
        # A typo'd policy name must not silently measure the wrong arm.
        with pytest.raises(ValueError, match="unknown retrieval policy"):
            policy_for_label("genrous")


class TestPolicyBench:
    """The bench is the artifact the cost claim rests on, so its invariants
    are tested rather than eyeballed once and trusted."""

    @staticmethod
    @pytest.fixture(scope="class")
    def arms():
        from backend.measurement.run_policy_bench import run_arm

        return {"tight": run_arm(TIGHT), "generous": run_arm(GENEROUS)}

    def test_both_arms_cover_the_whole_gold_set(self, arms):
        from backend.measurement.run_gate import GOLD_SET

        for arm in arms.values():
            assert arm["n_queries"] == len(GOLD_SET)

    def test_arms_are_comparable(self, arms):
        # Rule 1: same queries both sides, or the comparison is meaningless.
        tight_q = [r["query"] for r in arms["tight"]["per_query"]]
        generous_q = [r["query"] for r in arms["generous"]["per_query"]]
        assert tight_q == generous_q

    def test_recall_denominator_is_arm_independent(self, arms):
        # recall_true's denominator is the corpus, not the arm -- this is the
        # property that makes cross-arm comparison legitimate.
        for t, g in zip(arms["tight"]["per_query"], arms["generous"]["per_query"]):
            assert t["n_relevant_in_corpus"] == g["n_relevant_in_corpus"]

    def test_generous_retrieves_wider(self, arms):
        for t, g in zip(arms["tight"]["per_query"], arms["generous"]["per_query"]):
            assert g["n_retrieved"] >= t["n_retrieved"]

    def test_generous_never_loses_a_relevant_paper(self, arms):
        # Breadth is a superset of depth at the retrieval stage: a wider top_k
        # cannot drop a paper a narrower one surfaced.
        for t, g in zip(arms["tight"]["per_query"], arms["generous"]["per_query"]):
            assert g["n_relevant_retrieved"] >= t["n_relevant_retrieved"], t["query"]

    def test_generous_improves_rare_recall(self, arms):
        assert arms["generous"]["recall_true_rare"] > arms["tight"]["recall_true_rare"]

    def test_generous_does_not_cost_more(self, arms):
        # The headline. If this fails, GENEROUS is mis-tuned and the iso-cost
        # claim in policy.py's docstring is no longer true.
        assert arms["generous"]["total_prompt_tokens"] <= arms["tight"]["total_prompt_tokens"]
        assert arms["generous"]["total_summary_cost_usd"] <= arms["tight"]["total_summary_cost_usd"]

    def test_generous_fixes_zero_hit_queries(self, arms):
        assert arms["generous"]["zero_hit_queries"] < arms["tight"]["zero_hit_queries"]

    def test_tight_reproduces_the_published_compression_total(self, arms):
        # 42,401 tokens is the figure already published in
        # measurement/results/decision.md section 4. If this drifts, the two
        # documents disagree and one of them is wrong.
        assert arms["tight"]["total_prompt_tokens"] == 42401

    def test_token_counts_come_from_the_real_compressor(self, arms):
        for arm in arms.values():
            assert arm["total_prompt_tokens"] < arm["total_tokens_before_compression"]

    def test_comparison_reports_rescued_queries_explicitly(self, arms):
        from backend.measurement.run_policy_bench import compare

        delta = compare(arms["tight"], arms["generous"])
        assert delta["zero_hit_queries_fixed"]
        assert not delta["zero_hit_queries_introduced"]
        assert delta["cost_delta_pct"] <= 0
        assert delta["rare_recall_delta_pct"] > 0


class TestPipelineWiring:
    def test_policy_is_opt_in(self):
        # Default must stay None so nothing changes for callers that don't ask.
        import inspect

        from backend.app.pipeline import run_query

        assert inspect.signature(run_query).parameters["policy"].default is None

    def test_compression_rebuilds_rather_than_mutates(self):
        from backend.app.pipeline import _compress_for_policy
        from backend.contracts.fakes import FakeRetrieval

        papers = FakeRetrieval().search("corticobasal syndrome PET", top_k=5)
        originals = [sp.paper.abstract for sp in papers]

        compressed, before, after = _compress_for_policy(
            "corticobasal syndrome PET", papers, GENEROUS
        )

        # Frozen dataclasses: the originals must be untouched, because
        # check_citations verifies against the uncompressed source.
        assert [sp.paper.abstract for sp in papers] == originals
        assert after < before
        assert len(compressed) == len(papers)
        assert all(c.paper.pmid == o.paper.pmid for c, o in zip(compressed, papers))
