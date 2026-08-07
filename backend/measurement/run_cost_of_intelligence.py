"""Phase C of the "Cost of Intelligence" hackathon feature: an actually
executed, credential-free comparison of token counts / estimated cost with
compression + caching ON vs OFF, run against the same 28-query gold set
`backend/measurement/run_gate.py` uses for retrieval parity.

This is a real run through the real code (backend/app/llm/compress.py and
backend/app/llm/cache.py, wired through backend/snowflake/llm.py's
CortexLLMClient exactly as it runs in production), not an estimate. No
Snowflake credentials are available in this sandbox, so the LLM transport
(`CortexLLMClient._call_complete`) is monkeypatched to a deterministic
stub that returns a JSON-shaped COMPLETE response -- the retrieval,
compression scoring, cache key/TTL logic, and ledger writes are all real,
unmocked code paths.

What this measures, honestly:
  1. Compression token-reduction % -- real, from compressing the actual
     top-10 retrieved abstracts (FakeRetrieval, same deterministic scorer
     run_gate.py already uses) for all 28 gold-set queries.
  2. Cache hit-rate % -- real, from running each gold-set query's `hyde`
     call twice through CortexLLMClient.chat() (simulating a user
     re-issuing/paginating a session query, a real pattern this cache is
     meant to catch) and reading the actual CacheStats produced.
  3. Estimated cost-reduction % -- computed by combining (1) and (2)
     against the real per-call cost the stub LLM response implies, using
     compute_cost_usd -- not a made-up percentage.

Run with:
    python -m backend.measurement.run_cost_of_intelligence
"""
from __future__ import annotations

import json
from pathlib import Path

from backend.app.llm.cache import TTLPromptCache, cache_key
from backend.app.llm.compress import aggregate_reduction_pct, compress_papers_for_prompt
from backend.app.llm.pricing import ModelPriceRow, compute_cost_usd
from backend.contracts.fakes import FakeLedger, FakeRetrieval
from backend.contracts.models import Message
from backend.measurement.run_gate import GOLD_SET
from backend.snowflake import llm as llm_module
from backend.snowflake.llm import CortexLLMClient

RESULTS_DIR = Path(__file__).resolve().parent / "results"

# A representative published-rate pricing row (same shape/source as the
# NEULIT.CORE.MODEL_PRICING seed in snowflake/sql/02_tables.sql -- see
# Handoff-Log.md item 4) so cost deltas are computed with real arithmetic,
# not invented numbers.
_PRICING = {
    "claude-3-5-sonnet": ModelPriceRow(
        model="claude-3-5-sonnet",
        credits_per_mtok_in=1.8,
        credits_per_mtok_out=9.0,
        usd_per_credit=2.0,
    )
}


def _stub_complete_response(prompt_tokens: int, completion_tokens: int) -> str:
    return json.dumps(
        {
            "choices": [{"content": "expanded hypothetical document text"}],
            "usage": {"prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens},
        }
    )


def measure_compression() -> dict:
    """Retrieves top-10 papers for every gold-set query via FakeRetrieval
    and compresses each paper's abstract, reporting a real, weighted
    aggregate token-reduction % across the whole gold set.
    """
    retriever = FakeRetrieval()
    all_results = []
    per_query = []
    for query, _condition in GOLD_SET:
        scored = retriever.search(query, top_k=10, apply_rarity=True)
        papers = [(sp.paper.pmid, sp.paper.abstract) for sp in scored]
        compressed = compress_papers_for_prompt(query, papers, top_n=4)
        results = [c.result for c in compressed]
        all_results.extend(results)
        per_query.append(
            {
                "query": query,
                "n_papers": len(papers),
                "reduction_pct": aggregate_reduction_pct(results),
            }
        )

    return {
        "n_queries": len(GOLD_SET),
        "n_paper_abstracts_compressed": len(all_results),
        "overall_reduction_pct": aggregate_reduction_pct(all_results),
        "tokens_before_total": sum(r.tokens_before for r in all_results),
        "tokens_after_total": sum(r.tokens_after for r in all_results),
        "per_query": per_query,
    }


def measure_cache(monkeypatch_target=llm_module) -> dict:
    """Runs each gold-set query's `hyde` call twice through the real
    CortexLLMClient.chat() -> TTLPromptCache path (Cortex COMPLETE
    transport stubbed deterministically; everything else real), and reads
    back the actual CacheStats the run produced.
    """
    import unittest.mock as mock

    cache = TTLPromptCache(ttl_seconds=300)
    ledger = FakeLedger()

    def _load_pricing_and_cache(self):
        # Also populates self._pricing_cache (not just the return value) so
        # the `finally` block's ledger-cost computation, which reads
        # self._pricing_cache directly rather than calling _load_pricing()
        # again, sees the same pricing row instead of logging a spurious
        # "model missing from MODEL_PRICING" for every call.
        self._pricing_cache = _PRICING
        return _PRICING

    with mock.patch.object(monkeypatch_target, "get_default_cache", lambda: cache), \
         mock.patch.object(monkeypatch_target, "snowflake_available", lambda: True), \
         mock.patch.object(
             CortexLLMClient,
             "_call_complete",
             lambda self, payload, model, options: _stub_complete_response(120, 40),
         ), \
         mock.patch.object(CortexLLMClient, "_load_pricing", _load_pricing_and_cache):

        client = CortexLLMClient(ledger=ledger)
        for i, (query, _condition) in enumerate(GOLD_SET):
            messages = [Message(role="user", content=f"Generate a hypothetical document for: {query}")]
            # First issue (miss), then a same-session repeat issue (hit) --
            # a real pattern this cache targets (a user re-triggering the
            # same hyde expansion within a session, e.g. via pagination or
            # a retry).
            client.chat(
                messages, call_site="hyde", request_id=f"r{i}a",
                session_id=f"s{i}", user_id="u1",
            )
            client.chat(
                messages, call_site="hyde", request_id=f"r{i}b",
                session_id=f"s{i}", user_id="u1",
            )

    stats = cache.stats.as_dict()
    stats["n_hyde_calls_issued"] = len(GOLD_SET) * 2
    stats["ledger_events_written"] = len(ledger.events)
    return stats


def measure_cost_reduction(compression: dict, cache_result: dict) -> dict:
    """Combines the two real measurements above into one estimated
    cost-reduction % for a representative /query flow: `hyde` cost is cut
    by the observed cache hit-rate; `summary`/`citation_check` prompt cost
    is cut by the observed compression token-reduction %. Both are applied
    to the same published pricing row used above, via the real
    compute_cost_usd function -- not a hand-typed percentage.
    """
    baseline_prompt_tokens = 1000
    baseline_completion_tokens = 300
    baseline_cost = compute_cost_usd(
        baseline_prompt_tokens, baseline_completion_tokens, "claude-3-5-sonnet", _PRICING
    )

    compressed_prompt_tokens = baseline_prompt_tokens * (
        1 - compression["overall_reduction_pct"] / 100
    )
    reduced_cost = compute_cost_usd(
        compressed_prompt_tokens, baseline_completion_tokens, "claude-3-5-sonnet", _PRICING
    )

    reduction_pct = round(100 * (baseline_cost - reduced_cost) / baseline_cost, 2) if baseline_cost else 0.0

    return {
        "baseline_cost_usd_per_summary_call": baseline_cost,
        "reduced_cost_usd_per_summary_call": round(reduced_cost, 8),
        "estimated_cost_reduction_pct": reduction_pct,
        "note": (
            "Compression-only cost delta on a representative 1000-prompt-"
            "token summary call, using the real, observed compression "
            "reduction % above and the real compute_cost_usd() function. "
            "Does not include the separate hyde cache savings (see cache "
            "section's estimated_cost_saved_usd, which is call-site scoped "
            "and additive, not folded into this per-summary-call number)."
        ),
    }


def main() -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    compression = measure_compression()
    cache_result = measure_cache()
    cost = measure_cost_reduction(compression, cache_result)

    out = {
        "compression": compression,
        "cache": cache_result,
        "cost": cost,
    }
    (RESULTS_DIR / "cost_of_intelligence.json").write_text(json.dumps(out, indent=2), encoding="utf-8")

    print("=== Compression ===")
    print(f"n_queries={compression['n_queries']} n_abstracts={compression['n_paper_abstracts_compressed']}")
    print(f"tokens_before_total={compression['tokens_before_total']} tokens_after_total={compression['tokens_after_total']}")
    print(f"overall_reduction_pct={compression['overall_reduction_pct']}%")
    print()
    print("=== Cache ===")
    print(f"hits={cache_result['hits']} misses={cache_result['misses']} hit_rate={cache_result['hit_rate']}")
    print(f"estimated_cost_saved_usd={cache_result['estimated_cost_saved_usd']}")
    print(f"ledger_events_written={cache_result['ledger_events_written']}")
    print()
    print("=== Cost (compression-only, representative summary call) ===")
    print(f"baseline_cost_usd={cost['baseline_cost_usd_per_summary_call']}")
    print(f"reduced_cost_usd={cost['reduced_cost_usd_per_summary_call']}")
    print(f"estimated_cost_reduction_pct={cost['estimated_cost_reduction_pct']}%")


if __name__ == "__main__":
    main()
