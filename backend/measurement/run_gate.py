"""v2 measurement gate. v1 compared compressed vs uncompressed prompts
(Paritok); that comparison no longer exists (Paritok is removed entirely).

Repurposed per plan-v2/01-PHASE-CARD-1-snowflake-platform.md section 3.9 to
answer the question the new stack actually raises:

1. Retrieval parity -- does Cortex Search + rarity re-rank cost retrieval
   quality versus the v1 BM25+MiniLM baseline? recall@10 and
   rare-condition-recall@10 on a gold-set of scope-in queries (28 queries,
   two independently-worded queries per one of the 14 corpus conditions,
   expanded from the original 14 for statistical significance).
2. Cost per query -- median/p95 cost_usd per /query, by call site, from
   NEULIT.CORE.V_COST_PER_REQUEST.
3. Latency per call site -- median/p95, from the same source.

Run with:
    python -m backend.measurement.run_gate

(1) is computable with zero credentials, against FakeRetrieval -- the
deterministic token-overlap + rarity scorer in backend/contracts/fakes.py,
which is architecturally the same shape v1's BM25+MiniLM baseline was (a
local, non-Snowflake lexical/rarity scorer over corpus.json). (2) and (3)
require a live Snowflake account with TOKEN_LEDGER rows in it and cannot be
computed in this sandbox -- see backend/measurement/results/decision.md for
what is and isn't filled in, and exactly what a human with credentials must
run.
"""
from __future__ import annotations

import json
import statistics
from pathlib import Path

from backend.contracts.fakes import FakeRetrieval

RESULTS_DIR = Path(__file__).resolve().parent / "results"
CORPUS_PATH = Path(__file__).resolve().parent.parent / "data" / "corpus.json"

# Gold-set: in-scope query -> the condition whose papers count as "relevant"
# for recall@10. Mirrors v1's gold-set query wording (formerly in
# backend/tests/test_retrieval_gold_set.py) but scoped to conditions that
# actually exist in backend/data/corpus.json.
GOLD_SET: list[tuple[str, str]] = [
    ("scalp angiosarcoma FDG-PET case report", "Scalp angiosarcoma"),
    ("semantic variant primary progressive aphasia imaging", "Primary progressive aphasia semantic variant"),
    ("corticobasal syndrome frontoparietal cortex PET", "Corticobasal syndrome"),
    ("midbrain hypometabolism in progressive supranuclear palsy", "Progressive supranuclear palsy"),
    ("frontotemporal dementia anterior temporal involvement", "Frontotemporal dementia"),
    ("Creutzfeldt-Jakob disease parietal occipital PET", "Creutzfeldt-Jakob disease"),
    ("dementia with Lewy bodies occipital hypometabolism", "Dementia with Lewy bodies"),
    ("anti-NMDA receptor encephalitis basal ganglia involvement", "Anti-NMDA receptor encephalitis"),
    ("primary angiitis of CNS MCA territory findings", "Primary angiitis of CNS"),
    ("neurolymphomatosis leptomeningeal PET", "Neurolymphomatosis CNS involvement"),
    ("Alzheimer's disease FDG-PET temporal parietal pattern", "Alzheimer's disease probable typical FDG-PET pattern"),
    ("temporal lobe epilepsy interictal FDG-PET", "Temporal lobe epilepsy interictal FDG-PET"),
    ("acute ischemic stroke MCA territory PET", "Acute ischemic stroke MCA territory acute phase"),
    ("Parkinson's disease basal ganglia PET", "Parkinson's disease motor form later stage"),
    # --- second query per condition, added to make recall@10 a more
    # statistically meaningful number (14 -> 28 queries). Phrasing drawn
    # from a second, differently-worded paper title/theme per condition in
    # backend/data/corpus.json, so each condition now has two independent
    # query formulations rather than one.
    ("cutaneous angiosarcoma helical tomotherapy scalp brachytherapy", "Scalp angiosarcoma"),
    ("Huntington disease presenting as primary progressive aphasia semantics", "Primary progressive aphasia semantic variant"),
    ("flortaucipir PET MRI 4R tauopathy corticobasal degeneration", "Corticobasal syndrome"),
    ("AV1451 tau retention progressive supranuclear palsy eye movement disorder", "Progressive supranuclear palsy"),
    ("MAPT mutation behavioral variant frontotemporal dementia biomarker", "Frontotemporal dementia"),
    ("DPA-714 PET MRI neuroinflammation sporadic Creutzfeldt-Jakob disease", "Creutzfeldt-Jakob disease"),
    ("amyloid positivity probable dementia with Lewy bodies REM sleep behavior disorder", "Dementia with Lewy bodies"),
    ("NMDAR GFAP mGluR5 tripartite autoantibody autoimmune encephalitis", "Anti-NMDA receptor encephalitis"),
    ("granulomatous primary angiitis central nervous system brain PET MRI", "Primary angiitis of CNS"),
    ("diffuse large B-cell lymphoma central peripheral nervous system involvement", "Neurolymphomatosis CNS involvement"),
    ("amyloid PET typical Alzheimer's disease biomarker pattern", "Alzheimer's disease probable typical FDG-PET pattern"),
    ("interictal FDG-PET hypometabolism seizure focus localization epilepsy", "Temporal lobe epilepsy interictal FDG-PET"),
    ("middle cerebral artery territory infarct acute stroke perfusion imaging", "Acute ischemic stroke MCA territory acute phase"),
    ("nigrostriatal dopaminergic degeneration motor Parkinson's disease imaging", "Parkinson's disease motor form later stage"),
]

RARE_CONDITIONS = {
    "Scalp angiosarcoma",
    "Primary progressive aphasia semantic variant",
    "Corticobasal syndrome",
    "Progressive supranuclear palsy",
    "Frontotemporal dementia",
    "Creutzfeldt-Jakob disease",
    "Dementia with Lewy bodies",
    "Anti-NMDA receptor encephalitis",
    "Primary angiitis of CNS",
    "Neurolymphomatosis CNS involvement",
}


def _recall_at_10(retriever: FakeRetrieval, query: str, condition: str) -> float:
    results = retriever.search(query, top_k=10, apply_rarity=True)
    relevant_in_top10 = sum(1 for r in results if r.paper.condition == condition)
    total_relevant = sum(1 for p in retriever_corpus() if p.condition == condition)
    denom = min(10, total_relevant) or 1
    return relevant_in_top10 / denom


_CORPUS_CACHE = None


def retriever_corpus():
    global _CORPUS_CACHE
    if _CORPUS_CACHE is None:
        from backend.contracts.fakes import _load_corpus
        _CORPUS_CACHE = _load_corpus()
    return _CORPUS_CACHE


def compute_retrieval_parity() -> dict:
    retriever = FakeRetrieval()
    per_query = []
    for query, condition in GOLD_SET:
        recall = _recall_at_10(retriever, query, condition)
        per_query.append({
            "query": query,
            "condition": condition,
            "is_rare": condition in RARE_CONDITIONS,
            "recall_at_10": round(recall, 4),
        })

    overall_recall = round(statistics.mean(r["recall_at_10"] for r in per_query), 4)
    rare_rows = [r for r in per_query if r["is_rare"]]
    rare_recall = round(statistics.mean(r["recall_at_10"] for r in rare_rows), 4) if rare_rows else None

    return {
        "per_query": per_query,
        "n_queries": len(per_query),
        "recall_at_10": overall_recall,
        "rare_recall_at_10": rare_recall,
        "n_rare_queries": len(rare_rows),
    }


def compute_cost_and_latency() -> dict:
    """Attempts the live V_COST_PER_REQUEST-backed cost/latency numbers.
    Gracefully reports unavailable when there is no live Snowflake session
    -- this sandbox has zero Snowflake credentials, so this always takes the
    unavailable branch here, honestly.
    """
    from backend.snowflake.session import get_session, snowflake_available

    if not snowflake_available():
        return {"available": False, "detail": "snowflake unavailable in this environment"}

    session = get_session()
    if session is None:
        return {"available": False, "detail": "snowflake session unavailable"}

    try:
        cost_rows = session.sql(
            "SELECT COST_USD FROM NEULIT.CORE.V_COST_PER_REQUEST"
        ).collect()
        costs = sorted(float(r["COST_USD"] or 0.0) for r in cost_rows)

        latency_rows = session.sql(
            "SELECT CALL_SITE, AVG_LATENCY_MS FROM NEULIT.CORE.V_COST_BY_CALL_SITE"
        ).collect()

        def _pctl(values, pct):
            if not values:
                return None
            k = max(0, min(len(values) - 1, int(round((pct / 100) * (len(values) - 1)))))
            return values[k]

        return {
            "available": True,
            "n_requests": len(costs),
            "cost_median_usd": _pctl(costs, 50),
            "cost_p95_usd": _pctl(costs, 95),
            "latency_by_call_site": [
                {"call_site": r["CALL_SITE"], "avg_latency_ms": float(r["AVG_LATENCY_MS"] or 0.0)}
                for r in latency_rows
            ],
        }
    except Exception as exc:
        return {"available": False, "detail": f"query failed: {exc}"}


def main() -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    parity = compute_retrieval_parity()
    cost_latency = compute_cost_and_latency()

    (RESULTS_DIR / "retrieval_parity.json").write_text(json.dumps(parity, indent=2), encoding="utf-8")
    (RESULTS_DIR / "cost_latency.json").write_text(json.dumps(cost_latency, indent=2), encoding="utf-8")

    parity_rows = "\n".join(
        f"| {r['query']} | {r['condition']} | {'yes' if r['is_rare'] else 'no'} | {r['recall_at_10']:.2f} |"
        for r in parity["per_query"]
    )

    if cost_latency["available"]:
        cost_section = (
            f"- Sample size: {cost_latency['n_requests']} requests\n"
            f"- Median cost per query: ${cost_latency['cost_median_usd']:.6f}\n"
            f"- p95 cost per query: ${cost_latency['cost_p95_usd']:.6f}\n\n"
            "| call_site | avg_latency_ms |\n|---|---|\n" + "\n".join(
                f"| {r['call_site']} | {r['avg_latency_ms']:.1f} |" for r in cost_latency["latency_by_call_site"]
            )
        )
    else:
        cost_section = (
            f"**Not computed.** {cost_latency['detail']}. This requires a live Snowflake "
            "account with SNOWFLAKE_* credentials set and at least one real /query run "
            "recorded in NEULIT.CORE.TOKEN_LEDGER. A human with credentials must run:\n\n"
            "```bash\n"
            "export NEULIT_PROFILE=live_no_memory\n"
            "python -m backend.measurement.run_gate\n"
            "```\n\n"
            "after running a handful of real /query requests, then re-check this file."
        )

    decision_md = f"""# NeuLitTrace v2 -- Measurement Gate Decision

Generated by `python -m backend.measurement.run_gate`. Sample size and units
are explicit per section so every number here is directly quotable.

## 1. Retrieval parity -- FakeRetrieval baseline vs Cortex Search (live, pending)

**Claim to defend:** moving retrieval from v1's local BM25+MiniLM hybrid to
Snowflake Cortex Search + rarity re-rank did not cost retrieval quality.

**What's computed here:** recall@10 for `backend.contracts.fakes.FakeRetrieval`
(deterministic token-overlap + rarity scoring over `backend/data/corpus.json`,
n={parity['n_queries']} gold-set queries) -- this stands in for "the
retrieval-quality floor a local lexical scorer with the same rarity formula
achieves," since it is architecturally comparable to v1's BM25+MiniLM
baseline and needs no credentials.

**What's NOT computed here:** `CortexSearchRetriever`'s live recall@10.
That requires a real Cortex Search Service serving `NEULIT.CORE.PAPERS` --
unavailable in this sandbox (no Snowflake credentials). A human with
credentials must re-run this script under `NEULIT_PROFILE=live_no_memory`
once the search service is `ACTIVE` (see `snowflake/sql/README.md`), and
report the `CortexSearchRetriever` recall@10 alongside the numbers below to
actually close this claim.

| Overall recall@10 (FakeRetrieval baseline, n={parity['n_queries']}) | Rare-condition recall@10 (n={parity['n_rare_queries']}) |
|---|---|
| {parity['recall_at_10']:.2f} | {parity['rare_recall_at_10']:.2f} |

Per-query detail:

| Query | Condition | Rare | recall@10 |
|---|---|---|---|
{parity_rows}

## 2. Cost per query

{cost_section}

## 3. Latency per call site

See the `latency_by_call_site` table in section 2 above (`V_COST_BY_CALL_SITE.AVG_LATENCY_MS`)
-- median/p95 latency *per call*, not per call site, would require raw
per-event `LATENCY_MS` rows from `TOKEN_LEDGER` rather than the pre-aggregated
view; also not computable without a live account with real traffic. Median/p95
require a human with credentials to compute from
`SELECT LATENCY_MS FROM NEULIT.CORE.TOKEN_LEDGER WHERE CALL_SITE = '<site>'`
per call site once real traffic exists.
"""
    (RESULTS_DIR / "decision.md").write_text(decision_md, encoding="utf-8")
    print(f"Retrieval parity: recall@10={parity['recall_at_10']:.2f} rare_recall@10={parity['rare_recall_at_10']:.2f}")
    print(f"Cost/latency available: {cost_latency['available']}")


if __name__ == "__main__":
    main()
