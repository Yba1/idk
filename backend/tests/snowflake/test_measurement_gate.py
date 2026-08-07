"""Tier 1 -- credential-free. backend.measurement.run_gate's retrieval-parity
computation (the part of the gate that doesn't need live Snowflake).
"""
from __future__ import annotations

from backend.measurement.run_gate import GOLD_SET, RARE_CONDITIONS, compute_retrieval_parity


def test_gold_set_conditions_all_exist_in_corpus():
    from backend.contracts.fakes import _load_corpus

    corpus_conditions = {p.condition for p in _load_corpus()}
    for _, condition in GOLD_SET:
        assert condition in corpus_conditions


def test_compute_retrieval_parity_shape():
    result = compute_retrieval_parity()
    assert result["n_queries"] == len(GOLD_SET)
    assert 0.0 <= result["recall_at_10"] <= 1.0
    assert 0.0 <= result["rare_recall_at_10"] <= 1.0
    assert len(result["per_query"]) == len(GOLD_SET)


def test_rare_conditions_subset_of_gold_set_conditions():
    gold_conditions = {c for _, c in GOLD_SET}
    assert RARE_CONDITIONS.issubset(gold_conditions)


def test_compute_cost_and_latency_degrades_without_credentials(monkeypatch):
    from backend.measurement import run_gate

    result = run_gate.compute_cost_and_latency()
    assert "available" in result
    if not result["available"]:
        assert "detail" in result
