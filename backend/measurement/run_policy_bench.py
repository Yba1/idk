"""Retrieval-policy A/B bench -- does buying breadth instead of depth find the
rare paper, and what does it cost?

Run with:
    python -m backend.measurement.run_policy_bench

Two arms over the same 28-query gold set `run_gate.py` already publishes
against, with exactly one variable between them: where
`backend/app/retrieval/policy.py`'s two dials are set.

    TIGHT      top_k=10, compress_top_n=4   -- today's shipped behaviour
    GENEROUS   top_k=30, compress_top_n=1   -- the measured iso-cost point

`GENEROUS` is not hand-picked: the `_SWEEP` grid below is what located it. It
is the widest (top_k, compress_top_n) pair that still lands at or under TIGHT's
prompt-token budget, so the recall it buys is genuinely free rather than bought
with a bigger bill.

Zero credentials required. Retrieval is `backend.contracts.fakes.FakeRetrieval`
(deterministic token-overlap + the real rarity multiplier) and compression is
the real, unmocked `backend/app/llm/compress.py`. No LLM is called: this bench
measures what reaches the prompt, not what the model does with it. That is a
real limit and it is restated in the output.

--- THE THREE RULES, SAME AS backend/memex/engine.py ------------------------

1. BOTH ARMS SEE THE SAME QUERIES AND THE SAME CORPUS. The only variable is
   `top_k` / `compress_top_n`. Otherwise this measures corpus curation, not
   policy.
2. TOKENS ARE COUNTED ON THE COMPRESSED TEXT THAT WOULD ACTUALLY BE SENT --
   summed `CompressionResult.tokens_after` from the real compressor, not an
   estimate applied afterwards.
3. THE TIGHT ARM IS NOT SANDBAGGED. Its dials are the production retrieval
   breadth (`pipeline.RETRIEVAL_TOP_K` / `ports.search`'s default `top_k`, both
   10) and the compressor's own default (`compress.DEFAULT_TOP_N`, 4). If
   GENEROUS wins, it wins against the setting the system actually ships.

   Stated precisely, because it matters: TIGHT is not a replay of today's
   *summary prompt*. `pipeline.run_query` cuts to `SUMMARY_TOP_N = 5` papers
   before summarising and applies no compression at all -- `compress.py` is
   built, tested, and measured but was never wired into prompt assembly. So
   this bench compares two points in the policy space at the retrieval stage,
   which is where recall is won or lost; it does not reproduce the exact token
   count of a live summary call.

--- ON THE RECALL DENOMINATOR ----------------------------------------------

`run_gate.py` reports recall@10 with `denom = min(10, total_relevant)`. That
convention cannot be compared across arms: it would give TIGHT a denominator of
10 and GENEROUS a denominator of 40 for the same condition, so the two numbers
would not be measuring the same thing.

This bench therefore reports two, and labels both:

    recall_true      relevant retrieved / ALL relevant in corpus. Same
                     denominator for both arms, so this is the cross-arm
                     number. Note it is structurally capped for common
                     conditions -- Alzheimer's has 40 papers, so TIGHT's
                     recall_true cannot exceed 0.25 no matter how good it is.
    recall_capped    run_gate.py's convention, clamped to 1.0, carried purely
                     so this file's TIGHT arm can be checked against the
                     already-published 0.60 / 0.67 figures.

And the number that needs no denominator argument at all:

    zero_hit_queries  queries where the arm surfaced NOT ONE relevant paper.
                      This is the published failure mode from README.md's
                      founding citation, and it is binary.
"""
from __future__ import annotations

import json
import statistics
from pathlib import Path

from backend.app.llm.compress import compress_abstract
from backend.app.llm.pricing import compute_cost_usd
from backend.app.retrieval.policy import GENEROUS, TIGHT, RetrievalPolicy
from backend.contracts.fakes import FakeRetrieval
from backend.measurement.run_cost_of_intelligence import _PRICING
from backend.measurement.run_gate import GOLD_SET, RARE_CONDITIONS, retriever_corpus

RESULTS_DIR = Path(__file__).resolve().parent / "results"

# The summary call is the one this policy actually changes the size of, so its
# model is the right rate to price the delta at. Same row `run_gate.py` and
# `run_cost_of_intelligence.py` use.
_SUMMARY_MODEL = "claude-3-5-sonnet"

# Held constant across arms: policy changes the prompt, not the answer length.
_COMPLETION_TOKENS_PER_SUMMARY = 300

# Arms swept to locate the iso-cost frontier empirically rather than asserting
# it. TIGHT and GENEROUS are the two named policies; the rest exist so the
# breadth/depth trade can be read as a curve instead of two points.
_SWEEP: list[RetrievalPolicy] = [
    TIGHT,
    RetrievalPolicy(top_k=20, compress_top_n=2, label="k20n2"),
    GENEROUS,  # k=30, n=1 -- the iso-cost point this sweep is what identified
    RetrievalPolicy(top_k=40, compress_top_n=1, label="k40n1"),
    RetrievalPolicy(top_k=40, compress_top_n=2, label="k40n2"),
]


def _condition_totals() -> dict[str, int]:
    """Papers per condition in the corpus -- the recall denominator."""
    totals: dict[str, int] = {}
    for paper in retriever_corpus():
        totals[paper.condition] = totals.get(paper.condition, 0) + 1
    return totals


def run_arm(policy: RetrievalPolicy) -> dict:
    """One arm: every gold-set query retrieved and compressed under `policy`.

    Returns per-query rows plus the aggregates. Every token count comes from
    the real compressor; every cost comes from the real `compute_cost_usd`.
    """
    retriever = FakeRetrieval()
    totals = _condition_totals()
    rows: list[dict] = []

    for query, condition in GOLD_SET:
        scored = retriever.search(query, top_k=policy.top_k, apply_rarity=True)

        relevant = [sp for sp in scored if sp.paper.condition == condition]
        total_relevant = totals.get(condition, 0)

        recall_true = (len(relevant) / total_relevant) if total_relevant else 0.0
        capped_denom = min(10, total_relevant) or 1
        recall_capped = min(1.0, len(relevant) / capped_denom)

        # Rule 2: compress exactly what would be sent, count what comes back.
        compressions = [
            compress_abstract(query, sp.paper.abstract, top_n=policy.compress_top_n)
            for sp in scored
        ]
        tokens_before = sum(c.tokens_before for c in compressions)
        tokens_after = sum(c.tokens_after for c in compressions)
        n_skipped = sum(1 for c in compressions if c.skipped)

        rows.append(
            {
                "query": query,
                "condition": condition,
                "is_rare": condition in RARE_CONDITIONS,
                "n_retrieved": len(scored),
                "n_relevant_retrieved": len(relevant),
                "n_relevant_in_corpus": total_relevant,
                "recall_true": round(recall_true, 4),
                "recall_capped": round(recall_capped, 4),
                "zero_hit": len(relevant) == 0,
                "prompt_tokens": tokens_after,
                "tokens_before_compression": tokens_before,
                "n_abstracts_too_short_to_compress": n_skipped,
            }
        )

    rare_rows = [r for r in rows if r["is_rare"]]
    common_rows = [r for r in rows if not r["is_rare"]]
    total_prompt_tokens = sum(r["prompt_tokens"] for r in rows)

    # Cost of the summary call across the whole gold set, at the one rate the
    # policy actually moves. Completion tokens are held constant by design.
    total_cost = sum(
        compute_cost_usd(
            r["prompt_tokens"], _COMPLETION_TOKENS_PER_SUMMARY, _SUMMARY_MODEL, _PRICING
        )
        for r in rows
    )

    zero_hits = [r for r in rows if r["zero_hit"]]

    return {
        "policy": {
            "label": policy.label,
            "top_k": policy.top_k,
            "compress_top_n": policy.compress_top_n,
            "sentence_budget": policy.sentence_budget,
        },
        "n_queries": len(rows),
        "recall_true": round(statistics.mean(r["recall_true"] for r in rows), 4),
        "recall_true_rare": round(statistics.mean(r["recall_true"] for r in rare_rows), 4),
        "recall_true_common": round(statistics.mean(r["recall_true"] for r in common_rows), 4),
        "recall_capped": round(statistics.mean(r["recall_capped"] for r in rows), 4),
        "recall_capped_rare": round(statistics.mean(r["recall_capped"] for r in rare_rows), 4),
        "zero_hit_queries": len(zero_hits),
        "zero_hit_query_list": [r["query"] for r in zero_hits],
        "total_prompt_tokens": total_prompt_tokens,
        "mean_prompt_tokens_per_query": round(total_prompt_tokens / len(rows), 1),
        "total_tokens_before_compression": sum(r["tokens_before_compression"] for r in rows),
        "total_summary_cost_usd": round(total_cost, 8),
        "cost_usd_per_query": round(total_cost / len(rows), 8),
        "per_query": rows,
    }


def compare(tight: dict, generous: dict) -> dict:
    """The claim, computed rather than asserted.

    `recall_per_dollar` is the honest headline: absolute cost is not held
    perfectly equal by construction (the compressor refuses to trim abstracts
    under 3 sentences, so the sentence budget is an upper bound, not a
    guarantee), and quoting a raw recall gain while the bill moved would be the
    same sleight of hand this repo already refuses elsewhere.
    """
    t_cost = tight["total_summary_cost_usd"]
    g_cost = generous["total_summary_cost_usd"]
    t_tok = tight["total_prompt_tokens"]
    g_tok = generous["total_prompt_tokens"]

    def _pct(new: float, old: float) -> float:
        return round(100.0 * (new - old) / old, 2) if old else 0.0

    t_rpd = tight["recall_true_rare"] / t_cost if t_cost else 0.0
    g_rpd = generous["recall_true_rare"] / g_cost if g_cost else 0.0

    return {
        "token_delta_pct": _pct(g_tok, t_tok),
        "cost_delta_pct": _pct(g_cost, t_cost),
        "rare_recall_delta_pct": _pct(generous["recall_true_rare"], tight["recall_true_rare"]),
        "zero_hit_delta": generous["zero_hit_queries"] - tight["zero_hit_queries"],
        "zero_hit_queries_fixed": sorted(
            set(tight["zero_hit_query_list"]) - set(generous["zero_hit_query_list"])
        ),
        "zero_hit_queries_introduced": sorted(
            set(generous["zero_hit_query_list"]) - set(tight["zero_hit_query_list"])
        ),
        "rare_recall_per_dollar_tight": round(t_rpd, 2),
        "rare_recall_per_dollar_generous": round(g_rpd, 2),
        "rare_recall_per_dollar_delta_pct": _pct(g_rpd, t_rpd),
    }


def main() -> None:
    arms = {p.label: run_arm(p) for p in _SWEEP}
    tight, generous = arms[TIGHT.label], arms[GENEROUS.label]
    delta = compare(tight, generous)

    payload = {
        "arms": arms,
        "comparison_tight_vs_generous": delta,
        "method": {
            "retrieval": "backend.contracts.fakes.FakeRetrieval (deterministic, no credentials)",
            "compression": "backend.app.llm.compress.compress_abstract (real, unmocked)",
            "pricing": f"real compute_cost_usd() against the {_SUMMARY_MODEL} MODEL_PRICING row",
            "completion_tokens_held_constant": _COMPLETION_TOKENS_PER_SUMMARY,
            "not_measured": (
                "Answer quality. No LLM is called in this bench -- it measures what "
                "reaches the summary prompt, not what the model writes from it. "
                "Whether higher rare-condition recall in the prompt produces a better "
                "sourced summary requires a live run scored by citation_check, which "
                "needs Snowflake credentials."
            ),
        },
    }

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = RESULTS_DIR / "policy_bench.json"
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    print("=== Retrieval policy sweep (28-query gold set) ===")
    header = f"{'policy':<10} {'k':>3} {'n':>2} {'rare rec':>9} {'zero-hit':>9} {'tokens':>8} {'cost $':>10}"
    print(header)
    print("-" * len(header))
    for label, arm in arms.items():
        print(
            f"{label:<10} {arm['policy']['top_k']:>3} {arm['policy']['compress_top_n']:>2} "
            f"{arm['recall_true_rare']:>9.4f} {arm['zero_hit_queries']:>9} "
            f"{arm['total_prompt_tokens']:>8} {arm['total_summary_cost_usd']:>10.6f}"
        )

    print("\n=== TIGHT vs GENEROUS ===")
    print(f"prompt tokens      {tight['total_prompt_tokens']} -> {generous['total_prompt_tokens']} "
          f"({delta['token_delta_pct']:+.2f}%)")
    print(f"summary cost       ${tight['total_summary_cost_usd']:.6f} -> "
          f"${generous['total_summary_cost_usd']:.6f} ({delta['cost_delta_pct']:+.2f}%)")
    print(f"rare recall        {tight['recall_true_rare']:.4f} -> {generous['recall_true_rare']:.4f} "
          f"({delta['rare_recall_delta_pct']:+.2f}%)")
    print(f"zero-hit queries   {tight['zero_hit_queries']} -> {generous['zero_hit_queries']} "
          f"({delta['zero_hit_delta']:+d})")
    print(f"rare recall/$      {delta['rare_recall_per_dollar_tight']:.2f} -> "
          f"{delta['rare_recall_per_dollar_generous']:.2f} "
          f"({delta['rare_recall_per_dollar_delta_pct']:+.2f}%)")
    if delta["zero_hit_queries_fixed"]:
        print("\nqueries GENEROUS rescued from zero relevant papers:")
        for q in delta["zero_hit_queries_fixed"]:
            print(f"  + {q}")
    if delta["zero_hit_queries_introduced"]:
        print("\nqueries GENEROUS newly broke:")
        for q in delta["zero_hit_queries_introduced"]:
            print(f"  - {q}")

    print(f"\nRaw JSON: {out_path}")


if __name__ == "__main__":
    main()
