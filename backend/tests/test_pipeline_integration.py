"""End-to-end pipeline.run_query against the real fake-profile stack
(FakeRetrieval/FakeLLM/FakeMemory/FakeLedger), no mocking - the call-budget
assertion here is what protects the whole cost story from a silent
regression, per plan-v2/02-PHASE-CARD-2A-evermind-memory.md section 4.8.
"""
import pytest

from backend.app.pipeline import run_query
from backend.contracts.registry import get_services

DEMO_QUERY = "localized hypermetabolic uptake pattern on brain imaging"


@pytest.fixture(autouse=True)
def _fake_profile(monkeypatch):
    monkeypatch.setenv("NEULIT_PROFILE", "fake")
    get_services.cache_clear()
    yield
    get_services.cache_clear()


def test_non_refining_query_uses_six_or_fewer_calls_each_with_a_distinct_call_site():
    services = get_services()
    before = len(services.ledger.events)

    run_query(DEMO_QUERY, user_id="u1", session_id="s1", personalize=True)

    call_sites = [e.call_site for e in services.ledger.events[before:]]
    assert len(call_sites) <= 6
    assert len(call_sites) == len(set(call_sites))


def test_all_llm_calls_in_one_query_share_a_single_request_id():
    services = get_services()
    before = len(services.ledger.events)

    result = run_query(DEMO_QUERY, user_id="u1", session_id="s1", personalize=False)

    request_ids = {e.request_id for e in services.ledger.events[before:]}
    assert request_ids == {result.request_id}


def test_end_to_end_query_returns_a_populated_result():
    result = run_query(DEMO_QUERY, user_id="u1", session_id="s1", personalize=True)

    assert result.request_id
    assert len(result.trace) >= 1
    assert result.cost.total_tokens > 0
    assert result.cost.cost_usd > 0


def test_non_personalized_query_never_touches_memory_and_reports_applied_false():
    result = run_query(DEMO_QUERY, user_id="u1", session_id="s1", personalize=False)

    assert result.memory.applied is False
    assert result.memory.profile_used is False
    assert result.memory.distilled_context == ""
