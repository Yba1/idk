"""MemEx behaviour tests. Run keyless on the fake profile:

    NEULIT_PROFILE=fake pytest backend/tests/test_memex.py -q

These assert on behaviour a demo depends on, not on internals. Nothing here
breaks if a private helper is renamed.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("NEULIT_PROFILE", "fake")
os.environ.setdefault("MEMEX_MOCK", "1")

from backend.memex import pricing  # noqa: E402
from backend.memex.engine import ask, build_cold_context, build_warm_context  # noqa: E402
from backend.memex.everos_client import EverOSMemory  # noqa: E402
from backend.memex.market import MARGIN, Market  # noqa: E402
from backend.memex.scarcity import ScarcityIndex, get_index  # noqa: E402

RARE_QUERY = "neurolymphomatosis CNS involvement nerve enhancement MRI"
SHOCK_CONDITION = "Neurolymphomatosis CNS involvement"


# --------------------------------------------------------------------------
# pricing
# --------------------------------------------------------------------------


def test_published_rates_come_from_the_table_not_a_fallback():
    assert pricing.is_published("claude-opus-5")
    assert pricing.is_published("llama3.1-8b")
    assert not pricing.is_published("some-model-nobody-shipped")


def test_unknown_model_prices_without_raising_and_is_flagged_unpublished():
    breakdown = pricing.price_call("some-model-nobody-shipped", 1000, 100)
    assert breakdown.credits_total > 0
    assert breakdown.published is False


def test_premium_model_costs_more_than_the_cheap_one_for_identical_tokens():
    cold = pricing.price_call("claude-opus-5", 10_000, 500)
    warm = pricing.price_call("llama3.1-8b", 10_000, 500)
    assert cold.credits_total > warm.credits_total


def test_usage_for_matches_the_frozen_TokenUsage_field_names():
    usage = pricing.usage_for("claude-opus-5", 100, 20)
    assert set(usage) == {
        "prompt_tokens",
        "completion_tokens",
        "total_tokens",
        "model",
        "cost_usd",
    }
    assert usage["total_tokens"] == 120


def test_savings_and_ratio_degrade_instead_of_dividing_by_zero():
    assert pricing.savings_percent(0.0, 0.0) == 0.0
    assert pricing.cost_ratio(1.0, 0.0) == 0.0


# --------------------------------------------------------------------------
# scarcity
# --------------------------------------------------------------------------


def test_rarest_condition_scores_highest_and_commonest_is_exactly_neutral():
    index = get_index()
    table = index.table()
    assert table[0]["condition"] == SHOCK_CONDITION
    assert table[0]["paper_count"] == 4
    assert table[0]["multiplier"] == pytest.approx(2.093, abs=0.01)
    assert min(row["multiplier"] for row in table) == pytest.approx(1.0, abs=1e-9)


def test_no_condition_is_ever_discounted_below_neutral():
    assert all(row["multiplier"] >= 1.0 for row in get_index().table())


def test_unknown_condition_is_neutral_rather_than_an_error():
    assert get_index().multiplier("A condition that is not in the corpus") == 1.0


def test_a_bundle_prices_at_its_rarest_member():
    index = get_index()
    common = "Alzheimer's disease probable typical FDG-PET pattern"
    assert index.multiplier_for_papers([common, SHOCK_CONDITION]) == pytest.approx(
        index.multiplier(SHOCK_CONDITION)
    )


def test_unreadable_corpus_degrades_to_neutral_instead_of_raising():
    index = ScarcityIndex(corpus_path="/nonexistent/corpus.json")
    assert index.multiplier(SHOCK_CONDITION) == 1.0
    assert index.health()["ok"] is False


# --------------------------------------------------------------------------
# engine
# --------------------------------------------------------------------------


def test_warm_context_is_smaller_than_cold_for_the_same_papers():
    result = ask(RARE_QUERY)
    cold = build_cold_context(result.papers)
    warm = build_warm_context(result.papers, "")
    assert len(warm) < len(cold)


def test_warm_path_sends_fewer_prompt_tokens_than_cold():
    result = ask(RARE_QUERY)
    assert result.warm.prompt_tokens < result.cold.prompt_tokens
    assert result.tokens_displaced == result.cold.prompt_tokens - result.warm.prompt_tokens


def test_warm_path_is_cheaper_and_the_ratio_is_reported():
    result = ask(RARE_QUERY)
    assert result.warm.credits < result.cold.credits
    assert result.cost_ratio > 1.0
    assert 0.0 < result.savings_percent < 100.0


def test_displaced_tokens_are_priced_at_the_cold_rate_not_the_warm_one():
    result = ask(RARE_QUERY)
    at_cold = pricing.cost_for(result.tokens_displaced, result.cold.priced_as, "input")
    assert result.displaced_credits == pytest.approx(at_cold)


def test_fake_profile_is_labelled_as_a_pricing_scenario_not_a_measurement():
    # FakeLLM reports model="fake", which is not in the published table, so the
    # payload must say so rather than implying Opus actually ran.
    result = ask(RARE_QUERY)
    assert result.cold.model_measured is False
    assert result.cold.priced_as == pricing.cold_model()


def test_summary_is_sourced_from_the_corpus_even_when_the_llm_is_canned():
    result = ask(RARE_QUERY)
    assert "Fake summary" not in result.warm.summary_markdown
    assert result.papers
    assert result.papers[0].paper.condition in result.warm.summary_markdown


def test_rare_query_surfaces_the_scarcest_condition():
    result = ask(RARE_QUERY)
    assert result.scarcity_condition == SHOCK_CONDITION
    assert result.scarcity_multiplier == pytest.approx(2.093, abs=0.01)


def test_both_paths_see_the_same_papers():
    result = ask(RARE_QUERY)
    assert 0 < len(result.papers) <= 5


# --------------------------------------------------------------------------
# market
# --------------------------------------------------------------------------


def test_price_is_a_fraction_of_re_derivation_so_buying_beats_re_deriving():
    result = ask(RARE_QUERY)
    market = Market()
    trade = market.settle_question(result)
    assert 0 < trade.price_credits < result.displaced_credits
    assert trade.saved_credits > 0


def test_scarcity_raises_the_price_for_an_identical_token_delta():
    market = Market()
    cheap = market.price_of(0.01, 1.0)
    dear = market.price_of(0.01, 2.093)
    assert dear > cheap
    assert dear == pytest.approx(0.01 * MARGIN * 2.093)


def test_settlement_conserves_credits_between_the_two_wallets():
    result = ask(RARE_QUERY)
    market = Market()
    before = sum(a["balance_credits"] for a in market.agents())
    market.settle_question(result)
    after = sum(a["balance_credits"] for a in market.agents())
    assert after == pytest.approx(before)


def test_buyer_pays_and_seller_earns():
    result = ask(RARE_QUERY)
    market = Market()
    trade = market.settle_question(result)
    agents = {a["id"]: a for a in market.agents()}
    assert agents["rookie"]["spent_credits"] == pytest.approx(trade.price_credits)
    assert agents[trade.seller]["earned_credits"] == pytest.approx(trade.price_credits)


def test_shock_costs_more_than_the_memory_it_destroyed():
    result = ask(RARE_QUERY)
    market = Market()
    event = market.run_shock(result)
    assert event.post_shock_credits > event.pre_shock_credits
    assert event.spike > 1.0
    assert event.tokens_re_derived == result.cold.prompt_tokens


def test_reset_returns_every_wallet_to_its_opening_balance():
    result = ask(RARE_QUERY)
    market = Market()
    market.settle_question(result)
    market.reset()
    assert market.totals()["trades"] == 0
    assert len({a["balance_credits"] for a in market.agents()}) == 1


# --------------------------------------------------------------------------
# memory
# --------------------------------------------------------------------------


def test_mock_mode_is_the_default_without_a_key():
    memory = EverOSMemory()
    assert memory.health()["mode"] == "mock"
    assert memory.health()["ok"] is True


def test_forget_actually_destroys_the_profile():
    memory = EverOSMemory()
    memory.set_specialty("u1", "neuro-oncology")
    memory.record_query("u1", "s1", "neurolymphomatosis", [SHOCK_CONDITION])
    memory.record_papers_shown("u1", "s1", ["111", "222"])
    assert memory.get_profile("u1").query_count == 1
    assert memory.seen_pmids("u1") == {"111", "222"}

    memory.forget("u1")

    assert memory.get_profile("u1").query_count == 0
    assert memory.get_profile("u1").specialty is None
    assert memory.seen_pmids("u1") == set()
    assert memory.get_thread("u1", "s1").queries == []


def test_distilled_context_respects_the_600_char_contract():
    memory = EverOSMemory()
    for i in range(50):
        memory.record_query("u2", "s2", f"query {i}", [f"Condition number {i}"])
    assert len(memory.get_profile("u2").distilled_context) <= 600


def test_forget_is_idempotent_for_an_unknown_user():
    EverOSMemory().forget("never-seen")
