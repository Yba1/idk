# Handoff-Log — Card 1 (Snowflake platform)

Append-only. One entry per completed unit of work. This run had **no real
Snowflake account and no credentials** — everything below is honest about
what was actually executed (all Tier 1, credential-free) vs. what is
implemented-but-unexecuted and needs a human with real Snowflake
credentials to complete.

## Update — 2026-08-07: prompt caching + context compression ("Cost of
Intelligence" hackathon feature), still no Snowflake credentials

New feature added beyond original phase-card scope, for a hackathon demo
showing real % cost reduction. Three parts, all Tier 1 / credential-free
(no live Snowflake account was available or needed):

1. **Extractive context compression** — `backend/app/llm/compress.py`
   scores each sentence of a retrieved paper's abstract by query-term
   overlap (same tokenizer/overlap pattern as
   `backend/contracts/fakes.py`'s `_tokenize` and
   `backend/app/retrieval/rarity.py`'s boost logic — reused, not
   reinvented) and keeps the top-N (default 4) highest-scoring sentences
   per paper, in original order. Degrades to full text when a paper has
   too few sentences to safely trim. Instrumented with
   `backend/app/llm/tokenizer.py`'s existing `estimate_tokens` for real
   before/after token counts.

   **Not wired into prompt assembly.** `summary`/`citation_check` prompt
   assembly lives in `backend/app/pipeline.py`, which is **Card 2A
   ownership**, not Card 1's — per `scripts/ownership.txt`. Card 1 exposes
   `compress_papers_for_prompt(query, [(pmid, abstract), ...], top_n=...)`
   as a clean, independently-tested entry point; **Card 2A needs to call
   it** at the `summary` and `citation_check` call sites in
   `pipeline.py` (only those two — `hyde`/`relevance_check`/`refine`/
   `memory_distill` don't build multi-paper abstract prompts the same way)
   to actually realize the token savings in a live request. This is a
   genuine cross-lane hand-off, not a blocker Card 1 can resolve — flagged
   here rather than worked around by editing `pipeline.py`.

2. **In-process TTL prompt cache** — `backend/app/llm/cache.py`, hand-rolled
   dict + `time.monotonic()` TTL (no new pip dependency). Wired into
   `CortexLLMClient.chat()` (`backend/snowflake/llm.py`), scoped to `hyde`
   and `relevance_check` only. On a cache hit, the real Cortex COMPLETE
   call is skipped entirely and the cached `ChatResult` is returned; a
   `LedgerEvent` is still written (exactly one per `chat()` call, same
   invariant as before) but with token/cost fields zeroed for that event —
   `LedgerEvent` itself is untouched (frozen, no `cache_hit` field added,
   per the phase-card instruction). Hit/miss counts and an
   observed-avg-cost-derived savings estimate live in a separate
   `CacheStats` object (`cache_stats()`), not on the frozen model.

3. **Real measured numbers** —
   `backend/measurement/run_cost_of_intelligence.py` runs both of the
   above through their real code paths (only the Cortex COMPLETE
   transport call is stubbed, since there is no live account) against the
   same 28-query gold set `run_gate.py` uses, and reports actually-executed
   numbers (not estimates): **34.71% token reduction** from compression
   across 280 compressed paper abstracts, **50% cache hit-rate** from a
   synthetic 2-calls-per-query same-session-repeat pattern (28
   misses + 28 hits / 56 calls — see `backend/measurement/results/decision.md`
   section 4 for the full caveat on why this is a synthetic pattern, not an
   organic hit-rate claim), and **13.88% estimated cost reduction**
   (compression-only, on a representative summary-shaped call, computed via
   the real `compute_cost_usd()` and the researched `claude-3-5-sonnet`
   pricing row from item 4 below). Full command + output pasted into
   `backend/measurement/results/decision.md` section 4;
   `backend/measurement/results/cost_of_intelligence.json` has the raw
   numbers.

**Dashboard wiring:** `cache_stats()`'s shape does not fit
`/economics/summary`'s frozen response shape without an additive field —
proposed as a `Decisions.md` entry needing Card 2A/2B sign-off per the
section 4 "shape changes are logged, not made unilaterally" rule, rather
than wired in unilaterally. `backend/api/routes/economics.py` is untouched.

**Files added:** `backend/app/llm/compress.py`, `backend/app/llm/cache.py`,
`backend/measurement/run_cost_of_intelligence.py`,
`backend/tests/snowflake/test_compression.py`,
`backend/tests/snowflake/test_cache.py`.
**Files changed:** `backend/snowflake/llm.py` (cache wiring in `chat()`),
`backend/measurement/results/decision.md` (new section 4),
`Decisions.md` (new proposal entry), `Blockers.md` (new hand-off note).

## Update — second pass (this run), still no Snowflake credentials

Continued Card 1 on branch-1, again with zero Snowflake credentials in the
environment. What changed since the previous entry below:

- **Tier 2 `@pytest.mark.live` tests now exist**
  (`backend/tests/snowflake/test_live_snowflake.py`): real search-service
  round-trip on the CP1 gold-set query, one real `COMPLETE` call, one real
  ledger insert+read-back, one real Analyst question — all against the real
  `CortexSearchRetriever` / `CortexLLMClient` / `SnowflakeLedger` /
  `CortexAnalyst` classes with no mocking. All four are marked
  `@pytest.mark.live` and auto-skipped by
  `backend/tests/snowflake/conftest.py` unless `SNOWFLAKE_ACCOUNT` /
  `SNOWFLAKE_USER` / `SNOWFLAKE_PASSWORD` are all set — confirmed by running
  the full Tier 1 suite and seeing `4 skipped` with no
  `PytestUnknownMarkWarning`. No repo-root `pytest.ini` was added (outside
  Card 1's ownership bucket per `scripts/ownership.txt`); marker
  registration lives in the c1-owned `backend/tests/snowflake/conftest.py`
  instead. None of the four live tests were run — still no credentials.
- **Card 2A blocker in `Blockers.md` re-confirmed fresh**, with the exact
  current traceback (`ModuleNotFoundError: No module named
  'backend.app.llm_client'` importing `backend.api.main:app` under
  `NEULIT_PROFILE=fake`) and a copy-pasteable fix (route `get_llm_client()`
  / `get_retriever()` through `backend.contracts.registry.get_services()`
  instead of the deleted v1 classes). Still unresolved — not Card 1's file.
- **`MODEL_PRICING` seed in `snowflake/sql/02_tables.sql` updated** from an
  authoring-time placeholder to researched published Cortex AI Credit rates
  (1.8 credits/Mtok in, 9.0 credits/Mtok out, $2/credit, sourced and cited
  in the SQL comment) for both `claude-3-5-sonnet` and `claude-sonnet-4-5`.
  **Still list-price research, not an account-verified rate** — see item 4
  under "What a human with real Snowflake credentials must do" below,
  updated accordingly.
- **Retrieval-parity gold set expanded from 14 to 28 queries**
  (`backend/measurement/run_gate.py`'s `GOLD_SET`) — two independently
  worded queries per corpus condition instead of one, still computed
  entirely from `backend/data/corpus.json` with zero credentials via
  `FakeRetrieval`. Re-ran `python -m backend.measurement.run_gate`:
  **recall@10 = 0.60, rare_recall@10 = 0.67** (n=28, up from n=14's 0.59 /
  0.65) — `backend/measurement/results/decision.md` and
  `retrieval_parity.json` refreshed accordingly.
- **New `Decisions.md`** at repo root records the model-region-availability
  contingency plan (phase card §5 item 4) ahead of CP3 pressure: what to
  check, preference order for a substitute model, and the config/pricing/
  semantic-model steps to wire it through if `claude-3-5-sonnet` turns out
  to be unavailable in the account's Cortex region.
- **Tier 1 re-confirmed green**: `55 passed, 4 skipped` (the 4 new live
  tests), zero `SNOWFLAKE_*` env vars, same command as before (see below).
  `git diff --name-only contracts-v1..branch-1` re-checked — every changed
  path is inside the c1 bucket in `scripts/ownership.txt` (or `Blockers.md`
  / `Decisions.md` / `Handoff-Log.md` at repo root); no FROZEN file touched.

Still blocked on the same two things as before: a human with real Snowflake
credentials (everything under "What a human with real Snowflake credentials
must do to finish" below), and Card 2A resolving `backend/api/dependencies.py`
so `NEULIT_PROFILE=live_no_memory` can run `/query` end to end once
credentials exist.

## Summary status against phase card §6 Definition of Done

- [x] All four SQL files written (`snowflake/sql/01_setup.sql` through
      `04_views.sql` + `semantic_model.yaml` + `README.md` with run order).
      **Not run against a live account in this sandbox** — no credentials.
- [ ] `PAPERS` = 329 rows, `CONDITIONS` = 14 rows (10 rare) — **cannot be
      verified here.** `backend/app/corpus/build_corpus.py --to-snowflake`
      is implemented and unit-tested for its data-shaping logic
      (`test_build_corpus.py`), but the actual Snowflake write, and the
      `SELECT COUNT(*)` verification, need a human with credentials.
- [ ] Cortex Search Service `ACTIVE` and returning gold-set results —
      **not run.** No Snowflake account to create it in.
- [x] `CortexSearchRetriever`, `CortexLLMClient`, `SnowflakeLedger` all
      implement their `backend/contracts/ports.py` Protocols with no
      signature deviation (verified by import + the Tier 1 test suite
      constructing and calling each one against the real port signatures).
- [x] `exclude_pmids` verified applied before `top_k` truncation, by test
      — `backend/tests/snowflake/test_retrieval_contract.py::test_exclude_pmids_applied_before_truncation`.
- [x] Exactly one ledger event per `chat()` call, verified across
      success / retry-then-success / total-failure / snowflake-unavailable
      paths, by test — `backend/tests/snowflake/test_llm_contract.py`.
- [ ] `NEULIT_PROFILE=live_no_memory` runs a full `/query` end to end —
      **cannot be run.** No Snowflake credentials, and additionally
      `backend/api/dependencies.py` (Card 2A's file) currently fails to
      import at all under any profile because it still imports the deleted
      `backend.app.llm_client` / `backend.app.retrieval.hybrid` — see
      `Blockers.md`. This blocks `/query` end-to-end regardless of
      Snowflake credentials until Card 2A resolves it.
- [x] All four `/economics` endpoints implemented in
      `backend/api/routes/economics.py` against the frozen response shapes
      in `plan-v2/00-SHARED-CONTRACTS.md` §4, with `slowapi` rate limits
      (20/min `/economics/summary`, 6/min `/economics/ask`). Degrade to
      empty/zeroed responses (not 500s) when Snowflake is unavailable.
      **Not exercised against a live account.**
- [ ] Cortex Analyst answers all 5 verified queries — **not run.**
      `backend/snowflake/analyst.py`'s `CortexAnalyst.ask()` is implemented
      against the Cortex Analyst-over-COMPLETE call shape and degrades
      cleanly to an "unavailable" answer on any failure, but has never
      talked to a real semantic model. The 5 verified queries are written
      into `snowflake/sql/semantic_model.yaml`'s `verified_queries` block;
      a human with credentials needs to upload the semantic model file to
      a stage and confirm Analyst actually answers them.
- [x] Tier 1 tests green with **zero** Snowflake credentials in the
      environment: **55 passed** (see exact command + count below).
- [x] `git diff --name-only contracts-v1...branch-1` contains no path
      outside `plan-v2/00-SHARED-CONTRACTS.md` §3's Card 1 bucket and no
      FROZEN file (spot-checked at each commit; see `scripts/ownership.txt`
      cross-reference below).
- [x] `backend/measurement/results/decision.md` contains the
      retrieval-parity table (computed, real numbers) and the
      cost-per-query table (honestly marked "not computed here", with the
      exact command a human with credentials should run).

## What was actually run in this sandbox

```
cd C:\Users\vivaa\idk-card1
python -m venv .venv
.venv/Scripts/python -m pip install fastapi uvicorn pydantic slowapi numpy \
    pyyaml pytest pytest-asyncio httpx nilearn matplotlib
.venv/Scripts/python -m pytest backend/tests/snowflake \
    backend/tests/test_hybrid_retrieval.py \
    backend/tests/test_retrieval_gold_set.py \
    backend/tests/test_corpus_coverage.py \
    backend/tests/test_build_corpus.py \
    backend/tests/test_fetch_pubmed.py \
    backend/tests/test_llm_client.py \
    backend/tests/test_api_conditions.py -q
```

Result: **55 passed**, 1 unrelated deprecation warning (starlette/httpx),
zero `SNOWFLAKE_*` env vars set, `snowflake-snowpark-python` /
`snowflake-connector-python` **not installed** (not needed — `backend/snowflake/session.py`
imports them lazily inside `try/except ImportError`, confirmed by these
tests actually passing without the packages present).

```
.venv/Scripts/python -m backend.measurement.run_gate
```

Result:
```
Retrieval parity: recall@10=0.59 rare_recall@10=0.65
Cost/latency available: False
```
Full detail in `backend/measurement/results/decision.md`.

## What a human with real Snowflake credentials must do to finish

In order:

1. **Run the SQL DDL.** Follow `snowflake/sql/README.md` exactly:
   `01_setup.sql` → `02_tables.sql` → `python -m backend.app.corpus.build_corpus --to-snowflake`
   → `03_search_service.sql` → `04_views.sql`.
2. **Verify the corpus load.** Run the three `SELECT COUNT(*)` queries in
   `snowflake/sql/README.md`'s "Verification gate" section and paste the
   three numbers into this file (expect 329 / 14 / 10).
3. **Poll `SHOW CORTEX SEARCH SERVICES IN SCHEMA NEULIT.CORE;`** until
   `PAPERS_SEARCH` reports `ACTIVE`, then run
   `CortexSearchRetriever().search("asymmetric parietal hypometabolism on FDG-PET with progressive apraxia")`
   (the phase card's CP1 gold-set query) and paste a sample result here.
4. **Reconcile `MODEL_PRICING`.** `02_tables.sql` now seeds researched
   published rates (1.8 credits/Mtok in, 9.0 credits/Mtok out, $2/credit)
   for both `claude-3-5-sonnet` and `claude-sonnet-4-5`, sourced from public
   write-ups of Snowflake's post-2026-04-01 AI Credit Service Consumption
   Table (cited in the SQL comment) — **this is still a list-price research
   finding, not a verified account rate.** No live Snowflake account was
   available in this sandbox to check `SNOWFLAKE.ACCOUNT_USAGE` or the
   account's actual Cortex rate card, and `claude-3-5-sonnet` specifically
   did not have a distinctly-cited current rate in the search results used —
   `claude-sonnet-4-5`'s published rate was applied to both rows as the best
   available real-numbers proxy. A human with credentials MUST check
   `SNOWFLAKE.ACCOUNT_USAGE` / the account's real Cortex rate card and
   `UPDATE NEULIT.CORE.MODEL_PRICING` (or confirm the seeded values already
   match) before trusting any cost number this system reports — published
   list-price credit rates can differ from an account's actual billed rate.
5. **Confirm `claude-3-5-sonnet` is available on `COMPLETE`** in the
   account's region. If not, pick the best available model, set
   `SNOWFLAKE_CORTEX_MODEL` to it, and record the substitution in a
   `Decisions.md` entry (per plan-v2/01 §5 item 4) — the model name flows
   into `MODEL_PRICING` and the ledger.
6. **Resolve the Card 2A blocker in `Blockers.md`** (stale imports in
   `backend/api/dependencies.py`) — needed before `NEULIT_PROFILE=live_no_memory`
   can run a full `/query` end to end, which is otherwise ready on Card 1's
   side (`CortexSearchRetriever` + `CortexLLMClient` + `SnowflakeLedger` all
   implemented).
7. **Run `NEULIT_PROFILE=live_no_memory`** against `/query` end to end,
   paste `SELECT * FROM NEULIT.CORE.V_COST_PER_REQUEST LIMIT 5;` output
   here (this is the CP2 hand-off note Card 2B needs).
8. **Upload `snowflake/sql/semantic_model.yaml`** as a Cortex Analyst
   semantic model (Snowsight's Cortex Analyst setup, or the
   `SNOWFLAKE.CORTEX` semantic-model stage upload flow), point
   `SNOWFLAKE_SEMANTIC_MODEL_STAGE` at the resulting stage path, and run
   the 5 verified queries in that file through `POST /economics/ask`.
   Paste pass/fail for each of the 5 here.
9. **Re-run `python -m backend.measurement.run_gate`** with credentials set
   (`NEULIT_PROFILE=live_no_memory`) after step 7 has produced real traffic,
   to fill in the cost-per-query and latency-per-call-site sections of
   `backend/measurement/results/decision.md` that are currently marked "not
   computed here."
10. **Run the Tier 2 `@pytest.mark.live` tests** once they exist against a
    real account (none were written in this pass beyond the Tier 1 mocked
    contract tests — see "What was deliberately not attempted" below).

## What was deliberately not attempted in this sandbox

- **Running the Tier 2 `@pytest.mark.live` tests.** They now exist
  (`backend/tests/snowflake/test_live_snowflake.py`, added in the second
  pass — see the update note at the top of this file) but were never
  executed — still no Snowflake credentials in this sandbox. A human with
  real credentials should run
  `SNOWFLAKE_ACCOUNT=... SNOWFLAKE_USER=... SNOWFLAKE_PASSWORD=... pytest -m live backend/tests/snowflake/test_live_snowflake.py -v`
  and paste the results here, plus the CP1/CP2/CP3 hand-off notes each test
  is meant to produce (sample search result, cost/latency, ledger
  read-back, Analyst answer).
- Fabricating `SHOW CORTEX SEARCH SERVICES` output, row counts, or any
  other "as if it ran live" result. Every number in this file and in
  `backend/measurement/results/decision.md` that required a live Snowflake
  connection is explicitly marked unavailable rather than invented.

## Files touched (this run), by area

- `snowflake/sql/{01_setup,02_tables,03_search_service,04_views}.sql`,
  `snowflake/sql/semantic_model.yaml`, `snowflake/sql/README.md`
- `backend/snowflake/{session,retrieval,llm,ledger,analyst}.py`
- `backend/app/llm/{__init__,pricing,tokenizer,json_repair}.py`
- `backend/app/corpus/build_corpus.py` (now dual-mode: PubMed fetch, and
  `--to-snowflake` migration)
- `backend/app/retrieval/{condition_match,demo_fixture}.py` (rewritten
  against the deleted `hybrid.py`; `rarity.py` untouched, byte-identical to
  v1 as required)
- `backend/api/routes/{economics,conditions}.py`
- `config/snowflake.yaml`
- `backend/requirements-snowflake.txt`
- `backend/tests/snowflake/**` (new: `test_retrieval_contract.py`,
  `test_llm_contract.py`, `test_cost_math.py`, `test_ledger_buffer.py`,
  `test_health.py`, `test_measurement_gate.py`)
- `backend/tests/test_{hybrid_retrieval,retrieval_gold_set,llm_client,api_conditions}.py`
  (reassigned, rewritten against v2)
- `backend/measurement/run_gate.py` + `backend/measurement/results/*`
  (repurposed from the deleted Paritok A/B gate)
- `Blockers.md` (new)

**Second pass additions:**

- `backend/tests/snowflake/conftest.py` (new — `live` marker registration +
  auto-skip without `SNOWFLAKE_*` creds)
- `backend/tests/snowflake/test_live_snowflake.py` (new — Tier 2 tests)
- `Blockers.md` (sharpened with fresh traceback + fix suggestion)
- `snowflake/sql/02_tables.sql` (`MODEL_PRICING` seed updated with
  researched, cited rates)
- `backend/measurement/run_gate.py` + `backend/measurement/results/*`
  (gold set expanded 14 -> 28 queries, re-run)
- `Decisions.md` (new — model-region-availability contingency plan)
