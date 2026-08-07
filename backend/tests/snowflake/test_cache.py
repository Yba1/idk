"""Tier 1 -- credential-free. In-process TTL prompt cache (backend/app/llm/cache.py)
and its wiring into CortexLLMClient.chat() (backend/snowflake/llm.py).
"""
from __future__ import annotations

import json

from backend.app.llm.cache import (
    CACHEABLE_CALL_SITES,
    TTLPromptCache,
    cache_key,
    is_cacheable_call_site,
)
from backend.contracts.fakes import FakeLedger
from backend.contracts.models import ChatResult, Message, TokenUsage
from backend.snowflake import llm as llm_module
from backend.snowflake.llm import CortexLLMClient


def _messages(text="hello"):
    return [Message(role="user", content=text)]


# -- cache_key / normalization -------------------------------------------


def test_identical_normalized_prompts_produce_same_key():
    m1 = [Message(role="user", content="  what   is x?  ")]
    m2 = [Message(role="user", content="what is x?")]
    assert cache_key("hyde", "model-a", m1, None) == cache_key("hyde", "model-a", m2, None)


def test_session_ids_are_normalized_out_of_the_key():
    m1 = [Message(role="user", content="query for session_abc123")]
    m2 = [Message(role="user", content="query for session_xyz999")]
    assert cache_key("hyde", "model-a", m1, None) == cache_key("hyde", "model-a", m2, None)


def test_different_prompts_produce_different_keys():
    m1 = _messages("query A")
    m2 = _messages("query B")
    assert cache_key("hyde", "model-a", m1, None) != cache_key("hyde", "model-a", m2, None)


def test_different_call_site_or_model_changes_key():
    m = _messages("same text")
    assert cache_key("hyde", "model-a", m, None) != cache_key("relevance_check", "model-a", m, None)
    assert cache_key("hyde", "model-a", m, None) != cache_key("hyde", "model-b", m, None)


def test_only_hyde_and_relevance_check_are_cacheable():
    assert CACHEABLE_CALL_SITES == frozenset({"hyde", "relevance_check"})
    for site in ("summary", "citation_check", "refine", "memory_distill"):
        assert not is_cacheable_call_site(site)
    assert is_cacheable_call_site("hyde")
    assert is_cacheable_call_site("relevance_check")


# -- TTLPromptCache ---------------------------------------------------------


def _fake_result():
    return ChatResult(content="cached", usage=TokenUsage(1, 1, 2, "m", 0.01))


def test_cache_get_set_roundtrip():
    cache = TTLPromptCache(ttl_seconds=60)
    key = cache_key("hyde", "m", _messages(), None)
    assert cache.get(key) is None
    cache.set(key, _fake_result())
    assert cache.get(key) == _fake_result()


def test_cache_ttl_expiry_never_returns_stale_data(monkeypatch):
    cache = TTLPromptCache(ttl_seconds=10)
    key = cache_key("hyde", "m", _messages(), None)

    fake_now = {"t": 1000.0}
    monkeypatch.setattr("backend.app.llm.cache.time.monotonic", lambda: fake_now["t"])

    cache.set(key, _fake_result())
    assert cache.get(key) is not None

    fake_now["t"] += 11  # past TTL
    assert cache.get(key) is None
    assert len(cache) == 0  # lazily evicted


# -- CortexLLMClient wiring --------------------------------------------------


def _install_default_cache(monkeypatch):
    """Every test gets its own isolated default cache instance so hits from
    one test can never leak into another via the shared module-level cache.
    """
    fresh = TTLPromptCache(ttl_seconds=300)
    monkeypatch.setattr(llm_module, "get_default_cache", lambda: fresh)
    return fresh


def test_cache_hit_skips_cortex_call_for_hyde(monkeypatch):
    cache = _install_default_cache(monkeypatch)
    monkeypatch.setattr(llm_module, "snowflake_available", lambda: True)

    calls = {"n": 0}

    def fake_complete(self, payload, model, options):
        calls["n"] += 1
        return json.dumps(
            {"choices": [{"content": "hyde output"}], "usage": {"prompt_tokens": 5, "completion_tokens": 3}}
        )

    monkeypatch.setattr(CortexLLMClient, "_call_complete", fake_complete)
    monkeypatch.setattr(CortexLLMClient, "_load_pricing", lambda self: {})

    ledger = FakeLedger()
    client = CortexLLMClient(ledger=ledger)
    msgs = _messages("expand this query")

    r1 = client.chat(msgs, call_site="hyde", request_id="r1", session_id="s1", user_id="u1")
    r2 = client.chat(msgs, call_site="hyde", request_id="r2", session_id="s1", user_id="u1")

    assert calls["n"] == 1  # Cortex only actually called once
    assert r1.content == r2.content == "hyde output"
    assert len(ledger.events) == 2
    # second (cache-hit) ledger event has zero tokens/cost -- LedgerEvent
    # itself is unmodified (frozen, no cache_hit field); hit/miss tracked
    # in CacheStats separately.
    assert ledger.events[1].usage.prompt_tokens == 0
    assert ledger.events[1].usage.completion_tokens == 0
    assert ledger.events[1].usage.cost_usd == 0.0
    assert cache.stats.hits == 1
    assert cache.stats.misses == 1


def test_different_prompts_both_miss(monkeypatch):
    cache = _install_default_cache(monkeypatch)
    monkeypatch.setattr(llm_module, "snowflake_available", lambda: True)

    def fake_complete(self, payload, model, options):
        return json.dumps(
            {"choices": [{"content": "out"}], "usage": {"prompt_tokens": 1, "completion_tokens": 1}}
        )

    monkeypatch.setattr(CortexLLMClient, "_call_complete", fake_complete)
    monkeypatch.setattr(CortexLLMClient, "_load_pricing", lambda self: {})

    ledger = FakeLedger()
    client = CortexLLMClient(ledger=ledger)
    client.chat(_messages("query A"), call_site="hyde", request_id="r1", session_id="s1", user_id="u1")
    client.chat(_messages("query B"), call_site="hyde", request_id="r2", session_id="s1", user_id="u1")

    assert cache.stats.hits == 0
    assert cache.stats.misses == 2


def test_non_cacheable_call_sites_always_miss_cortex(monkeypatch):
    """summary/citation_check/refine/memory_distill must never be served
    from cache, even when called twice with identical messages.
    """
    cache = _install_default_cache(monkeypatch)
    monkeypatch.setattr(llm_module, "snowflake_available", lambda: True)

    calls = {"n": 0}

    def fake_complete(self, payload, model, options):
        calls["n"] += 1
        return json.dumps(
            {"choices": [{"content": "out"}], "usage": {"prompt_tokens": 1, "completion_tokens": 1}}
        )

    monkeypatch.setattr(CortexLLMClient, "_call_complete", fake_complete)
    monkeypatch.setattr(CortexLLMClient, "_load_pricing", lambda self: {})

    ledger = FakeLedger()
    client = CortexLLMClient(ledger=ledger)
    msgs = _messages("summarize these papers")

    client.chat(msgs, call_site="summary", request_id="r1", session_id="s1", user_id="u1")
    client.chat(msgs, call_site="summary", request_id="r2", session_id="s1", user_id="u1")

    assert calls["n"] == 2  # Cortex called every time, never cached
    assert cache.stats.hits == 0
    assert cache.stats.misses == 0  # not cacheable -- no cache bookkeeping at all
    assert len(cache) == 0
