# Handoff-Log — Card 1 (Snowflake platform)

Append-only. One entry per completed unit of work. This run had **no real
Snowflake account and no credentials** — everything below is honest about
what was actually executed (all Tier 1, credential-free) vs. what is
implemented-but-unexecuted and needs a human with real Snowflake
credentials to complete.

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
4. **Reconcile `MODEL_PRICING`.** `02_tables.sql` seeds a *placeholder*
   credit rate for `claude-3-5-sonnet` (3.0 credits/Mtok in, 15.0 out, $2/credit)
   copied from a generic published rate card at authoring time, not the
   account's actual Cortex consumption pricing. Check
   `SNOWFLAKE.ACCOUNT_USAGE` / the account's real Cortex rate card and
   `UPDATE NEULIT.CORE.MODEL_PRICING` before trusting any cost number this
   system reports.
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

- **Tier 2 `@pytest.mark.live` tests.** The phase card asks for these to be
  *written* (marked `@pytest.mark.live`) even though they can't run here.
  They were not added in this pass — Tier 1 coverage (mocked Snowpark
  sessions) is complete for `CortexSearchRetriever`, `CortexLLMClient`,
  `SnowflakeLedger`, `CortexAnalyst`, and cost math. A follow-up pass with
  real credentials should add live round-trip tests per phase card §3.10
  Tier 2 (real search service round-trip, one real `COMPLETE`, one real
  ledger insert+read-back, one real Analyst question) before this is fully
  done per §6.
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
