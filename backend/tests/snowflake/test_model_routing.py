"""Tier 1 -- credential-free. Phase E call-site model routing
(backend/app/llm/routing.py) and its wiring into CortexLLMClient.chat()
(backend/snowflake/llm.py).
"""
from __future__ import annotations

import json

from backend.app.llm.cache import TTLPromptCache
from backend.app.llm.routing import (
    CHEAP_CALL_SITES,
    STRONG_CALL_SITES,
    model_for_call_site,
)
from backend.contracts.fakes import FakeLedger
from backend.contracts.models import Message
from backend.snowflake import llm as llm_module
from backend.snowflake.llm import CortexLLMClient


def _messages():
    return [Message(role="user", content="hello")]


def _install_fresh_cache(monkeypatch):
    # These tests exercise chat()'s model routing on hyde/relevance_check,
    # which are cache-eligible call sites -- use an isolated cache instance
    # per test (same pattern as test_cache.py's _install_default_cache) so
    # a cached entry from another test module doesn't mask a real Cortex
    # call and produce a false pass/fail here.
    fresh = TTLPromptCache(ttl_seconds=300)
    monkeypatch.setattr(llm_module, "get_default_cache", lambda: fresh)
    return fresh


# -- tier membership --------------------------------------------------------


def test_tier_membership_matches_phase_card():
    assert CHEAP_CALL_SITES == frozenset({"relevance_check", "hyde"})
    assert STRONG_CALL_SITES == frozenset(
        {"summary", "citation_check", "refine", "memory_distill"}
    )
    assert CHEAP_CALL_SITES.isdisjoint(STRONG_CALL_SITES)


# -- model_for_call_site: no env vars set (hardcoded defaults) --------------


def test_defaults_no_env_vars(monkeypatch):
    monkeypatch.delenv("SNOWFLAKE_CORTEX_MODEL", raising=False)
    monkeypatch.delenv("SNOWFLAKE_CORTEX_MODEL_CHEAP", raising=False)
    monkeypatch.delenv("SNOWFLAKE_CORTEX_MODEL_STRONG", raising=False)

    assert model_for_call_site("relevance_check") == "mistral-7b"
    assert model_for_call_site("hyde") == "mistral-7b"
    assert model_for_call_site("summary") == "claude-3-5-sonnet"
    assert model_for_call_site("citation_check") == "claude-3-5-sonnet"
    assert model_for_call_site("refine") == "claude-3-5-sonnet"
    assert model_for_call_site("memory_distill") == "claude-3-5-sonnet"


# -- backward compat: only SNOWFLAKE_CORTEX_MODEL set ------------------------


def test_single_model_env_var_used_for_both_tiers_when_only_it_is_set(monkeypatch):
    monkeypatch.setenv("SNOWFLAKE_CORTEX_MODEL", "claude-sonnet-4-5")
    monkeypatch.delenv("SNOWFLAKE_CORTEX_MODEL_CHEAP", raising=False)
    monkeypatch.delenv("SNOWFLAKE_CORTEX_MODEL_STRONG", raising=False)

    assert model_for_call_site("hyde") == "claude-sonnet-4-5"
    assert model_for_call_site("relevance_check") == "claude-sonnet-4-5"
    assert model_for_call_site("summary") == "claude-sonnet-4-5"
    assert model_for_call_site("memory_distill") == "claude-sonnet-4-5"


# -- tier-specific env vars take priority over the single var ---------------


def test_tier_specific_env_vars_override_single_var(monkeypatch):
    monkeypatch.setenv("SNOWFLAKE_CORTEX_MODEL", "should-not-be-used")
    monkeypatch.setenv("SNOWFLAKE_CORTEX_MODEL_CHEAP", "cheap-model-x")
    monkeypatch.setenv("SNOWFLAKE_CORTEX_MODEL_STRONG", "strong-model-y")

    assert model_for_call_site("hyde") == "cheap-model-x"
    assert model_for_call_site("relevance_check") == "cheap-model-x"
    assert model_for_call_site("summary") == "strong-model-y"
    assert model_for_call_site("citation_check") == "strong-model-y"
    assert model_for_call_site("refine") == "strong-model-y"
    assert model_for_call_site("memory_distill") == "strong-model-y"


def test_only_cheap_override_set_strong_falls_back_to_single_then_default(monkeypatch):
    monkeypatch.delenv("SNOWFLAKE_CORTEX_MODEL", raising=False)
    monkeypatch.setenv("SNOWFLAKE_CORTEX_MODEL_CHEAP", "cheap-model-x")
    monkeypatch.delenv("SNOWFLAKE_CORTEX_MODEL_STRONG", raising=False)

    assert model_for_call_site("hyde") == "cheap-model-x"
    assert model_for_call_site("summary") == "claude-3-5-sonnet"  # hardcoded default


# -- wiring into CortexLLMClient.chat() --------------------------------------


def test_chat_selects_cheap_model_for_hyde(monkeypatch):
    _install_fresh_cache(monkeypatch)
    monkeypatch.delenv("SNOWFLAKE_CORTEX_MODEL", raising=False)
    monkeypatch.delenv("SNOWFLAKE_CORTEX_MODEL_CHEAP", raising=False)
    monkeypatch.delenv("SNOWFLAKE_CORTEX_MODEL_STRONG", raising=False)
    monkeypatch.setattr(llm_module, "snowflake_available", lambda: True)

    captured = {}

    def capture_complete(self, payload, model, options):
        captured["model"] = model
        return json.dumps(
            {"choices": [{"content": "hi"}], "usage": {"prompt_tokens": 5, "completion_tokens": 3}}
        )

    monkeypatch.setattr(CortexLLMClient, "_call_complete", capture_complete)
    monkeypatch.setattr(CortexLLMClient, "_load_pricing", lambda self: {})

    ledger = FakeLedger()
    client = CortexLLMClient(ledger=ledger)
    result = client.chat(_messages(), call_site="hyde", request_id="r1", session_id="s1", user_id="u1")

    assert captured["model"] == "mistral-7b"
    assert result.usage.model == "mistral-7b"
    assert len(ledger.events) == 1
    assert ledger.events[0].usage.model == "mistral-7b"


def test_chat_selects_strong_model_for_summary(monkeypatch):
    monkeypatch.delenv("SNOWFLAKE_CORTEX_MODEL", raising=False)
    monkeypatch.delenv("SNOWFLAKE_CORTEX_MODEL_CHEAP", raising=False)
    monkeypatch.delenv("SNOWFLAKE_CORTEX_MODEL_STRONG", raising=False)
    monkeypatch.setattr(llm_module, "snowflake_available", lambda: True)

    captured = {}

    def capture_complete(self, payload, model, options):
        captured["model"] = model
        return json.dumps(
            {"choices": [{"content": "summary text"}], "usage": {"prompt_tokens": 50, "completion_tokens": 20}}
        )

    monkeypatch.setattr(CortexLLMClient, "_call_complete", capture_complete)
    monkeypatch.setattr(CortexLLMClient, "_load_pricing", lambda self: {})

    ledger = FakeLedger()
    client = CortexLLMClient(ledger=ledger)
    result = client.chat(_messages(), call_site="summary", request_id="r2", session_id="s1", user_id="u1")

    assert captured["model"] == "claude-3-5-sonnet"
    assert result.usage.model == "claude-3-5-sonnet"
    assert len(ledger.events) == 1
    assert ledger.events[0].usage.model == "claude-3-5-sonnet"


def test_chat_respects_tier_env_var_overrides(monkeypatch):
    _install_fresh_cache(monkeypatch)
    monkeypatch.setenv("SNOWFLAKE_CORTEX_MODEL_CHEAP", "cheap-override")
    monkeypatch.setenv("SNOWFLAKE_CORTEX_MODEL_STRONG", "strong-override")
    monkeypatch.setattr(llm_module, "snowflake_available", lambda: True)

    def make_complete(expected_model):
        def _complete(self, payload, model, options):
            assert model == expected_model
            return json.dumps({"choices": [{"content": "x"}], "usage": {"prompt_tokens": 1, "completion_tokens": 1}})
        return _complete

    monkeypatch.setattr(CortexLLMClient, "_load_pricing", lambda self: {})

    ledger = FakeLedger()
    client = CortexLLMClient(ledger=ledger)

    monkeypatch.setattr(CortexLLMClient, "_call_complete", make_complete("cheap-override"))
    r1 = client.chat(_messages(), call_site="relevance_check", request_id="r3", session_id="s1", user_id="u1")
    assert r1.usage.model == "cheap-override"

    monkeypatch.setattr(CortexLLMClient, "_call_complete", make_complete("strong-override"))
    r2 = client.chat(_messages(), call_site="citation_check", request_id="r4", session_id="s1", user_id="u1")
    assert r2.usage.model == "strong-override"


def test_chat_single_model_env_var_backward_compat(monkeypatch):
    _install_fresh_cache(monkeypatch)
    monkeypatch.setenv("SNOWFLAKE_CORTEX_MODEL", "claude-sonnet-4-5")
    monkeypatch.delenv("SNOWFLAKE_CORTEX_MODEL_CHEAP", raising=False)
    monkeypatch.delenv("SNOWFLAKE_CORTEX_MODEL_STRONG", raising=False)
    monkeypatch.setattr(llm_module, "snowflake_available", lambda: True)
    monkeypatch.setattr(
        CortexLLMClient,
        "_call_complete",
        lambda self, payload, model, options: json.dumps(
            {"choices": [{"content": "x"}], "usage": {"prompt_tokens": 1, "completion_tokens": 1}}
        ),
    )
    monkeypatch.setattr(CortexLLMClient, "_load_pricing", lambda self: {})

    ledger = FakeLedger()
    client = CortexLLMClient(ledger=ledger)

    for call_site in ("hyde", "relevance_check", "summary", "citation_check", "refine", "memory_distill"):
        result = client.chat(
            _messages(), call_site=call_site, request_id=f"r-{call_site}", session_id="s1", user_id="u1"
        )
        assert result.usage.model == "claude-sonnet-4-5"
