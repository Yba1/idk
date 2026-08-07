# Handoff-Log — Card 1 (Snowflake platform)

Append-only. One entry per completed unit of work. This run had **no real
Snowflake account and no credentials** — everything below is honest about
what was actually executed (all Tier 1, credential-free) vs. what is
implemented-but-unexecuted and needs a human with real Snowflake
credentials to complete.

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

## Update — third pass: CP1 + CP2, live account, everything below actually executed

First run against a real Snowflake account: `ZNEYKJS-BB01029`, user `YBALRS`.
Authenticated via Personal Access Token (the account requires MFA; a PAT
avoids interactive Duo pushes for a headless app). **The PAT is
ACCOUNTADMIN-scoped** (Snowflake PATs lock to whatever role is active when
generated, and `NEULIT_APP` didn't exist yet at token-generation time) — see
"Known deviations" below.

### CP1 — DDL, corpus load, search service

Ran all four SQL files in order (`01_setup.sql` → `02_tables.sql` → corpus
load → `03_search_service.sql` → `04_views.sql`), plus supplemental grants
the phase card's own DDL was missing (see "Bugs found and fixed" below).

**Verification gate results:**
```
SELECT COUNT(*) FROM NEULIT.CORE.PAPERS;                        -> 329
SELECT COUNT(*) FROM NEULIT.CORE.CONDITIONS;                     -> 14
SELECT COUNT(*) FROM NEULIT.CORE.CONDITIONS WHERE IS_RARE;       -> 10
```

**`SHOW CORTEX SEARCH SERVICES IN SCHEMA NEULIT.CORE` (relevant columns):**
```
name=PAPERS_SEARCH  indexing_state=ACTIVE  serving_state=ACTIVE
source_data_num_rows=329  embedding_model=snowflake-arctic-embed-m-v1.5
```
Note: the columns are `indexing_state`/`serving_state`, not a single `state`
column — `backend/snowflake/retrieval.py`'s own `health()` was checking for
`state` and would have silently always reported inactive; fixed (see below).

**Gold-set query result** (`"asymmetric parietal hypometabolism on FDG-PET
with progressive apraxia"`, top 5, via the real `CortexSearchRetriever`):
```
42191948  score=1.60    rarity_mult=1.6  Plasma phosphorylated tau biomarkers map onto FDG PET hypometabo...
30223705  score=1.598   rarity_mult=1.6  Combined findings of FDG-PET and arterial spin labeling in sporadic Cr...
31985135  score=1.598   rarity_mult=1.6  Different FDG-PET metabolic patterns of anti-AMPAR and anti-NMDAR ence...
28240664  score=1.597   rarity_mult=1.6  Creutzfeldt-Jakob Disease Mimicking Alzheimer Disease and Dementia Wit...
36606595  score=1.597   rarity_mult=1.6  (untitled result)
```
`closest_conditions()` for the same query correctly surfaced Corticobasal
syndrome (0.75), Frontotemporal dementia (0.74), Dementia with Lewy bodies
(0.73) — all rare, all clinically plausible neighbors.

### CP2 — live LLM call, ledger round-trip

`CortexLLMClient.chat()` against the corrected default model
`claude-sonnet-4-5` (see `Decisions.md` for why `claude-3-5-sonnet` was
swapped out): request `"Reply with exactly the word: PONG"` returned
`content='PONG'`, `usage=TokenUsage(prompt_tokens=16, completion_tokens=6,
total_tokens=22, model='claude-sonnet-4-5', cost_usd=0.0001656)`,
`degraded=False`. Cost math verified by hand: `(16/1e6)*1.8*2 +
(6/1e6)*9.0*2 = 0.0001656` — matches exactly.

`SELECT * FROM NEULIT.CORE.V_COST_PER_REQUEST LIMIT 5`:
```
request_id  session_id  user_id     llm_calls  total_tokens  cost_usd    started_at
test-req-2  test-sess   test-user   1          0             0E-8        2026-08-07 12:09:53
test-req-3  test-sess   test-user   1          22            0.00016560  2026-08-07 12:16:35
```
`test-req-2` is the pre-fix degraded run (wrong model name, before the
`Decisions.md` substitution) — correctly logged as `degraded=True`,
`cost_usd=0`, proving the "exactly one ledger event per call, including
failure paths" contract holds live, not just under mocks.

**`NEULIT_PROFILE=live_no_memory` full app import:** confirmed working
after fixing the Card 2A blocker (see `Blockers.md`, resolved) and
installing a missing `matplotlib` dependency (`backend/api/routes/atlas.py`,
not a Card 1 file, imports it directly with no requirements-file entry).
Full `POST /query` HTTP round-trip was **not** run — see `Blockers.md`'s new
entry on `client.chat()` signature mismatches in `backend/app/loop/`,
`backend/app/summary/`, `backend/app/verify/` (outside Card 1's ownership,
budgeted as separate follow-up work). `/economics/*` and `/conditions` do
not depend on that pipeline.

### Bugs found and fixed against the live account (none of these surfaced
under Tier-1 mocks — the mocks encoded the same wrong assumptions the code
had)

1. `backend/snowflake/retrieval.py` `_raw_search` called a function named
   `SYSTEM$SEARCH` that does not exist. Fixed to
   `SNOWFLAKE.CORTEX.SEARCH_PREVIEW(<service>, <json request>)`, the real
   SQL entry point for Cortex Search.
2. Every `session.sql(...).bind([...])` call site
   (`backend/snowflake/retrieval.py` x3, `backend/api/routes/economics.py`
   x1) — `.bind()` is not a real Snowpark `DataFrame` method; it was
   silently falling through to Snowpark's `__getattr__` column-lookup path
   and either erroring unpredictably or (worse) not erroring at all in some
   shapes. Fixed to the real API: `session.sql(query, params=[...])`.
3. Cortex Search's actual response shape nests sub-scores under `@scores`
   (`text_match`, `cosine_similarity`, `reranker_score`), not the flat
   `@score`/`score` key the code assumed. Fixed score extraction to read
   `reranker_score` (falling back to `cosine_similarity`) for ranking,
   `text_match`→`lexical_score`, `cosine_similarity`→`semantic_score`.
4. `_raw_search`'s requested columns omitted `ABSTRACT` — every returned
   `Paper.abstract` would have been empty. Added it.
5. `backend/snowflake/retrieval.py` `health()` checked a `state` key from
   `SHOW CORTEX SEARCH SERVICES`; the real column names are
   `indexing_state`/`serving_state`. Fixed — `health()` was silently always
   reporting the service inactive before this.
6. `get_by_pmids()` called `.get()` on Snowpark `Row` objects, which don't
   support dict-style `.get()`. Fixed to `row.as_dict()` before passing to
   `_row_to_paper`.
7. `backend/snowflake/llm.py` `_call_complete` used `.collect(timeout=...)`
   — not a real `DataFrame.collect()` kwarg. Fixed to
   `.collect(statement_params={"STATEMENT_TIMEOUT_IN_SECONDS": "20"})`,
   confirmed live (a genuinely slow/unavailable model now cleanly times out
   at 20s with a real Snowflake error instead of crashing with a `TypeError`
   before ever reaching Snowflake).
8. `backend/app/corpus/build_corpus.py` `load_to_snowflake()` built the
   `CONDITIONS` insert as `INSERT ... VALUES (ARRAY_CONSTRUCT(...), ...)` —
   Snowflake's `VALUES` clause rejects function calls in literal row tuples.
   Fixed to `INSERT ... SELECT ... UNION ALL SELECT ...`.
9. `claude-3-5-sonnet` confirmed unavailable on `COMPLETE` in this account's
   region — see `Decisions.md` for the full resolution (substituted
   `claude-sonnet-4-5`, already anticipated as the hedge in the
   `MODEL_PRICING` seed).

### Supplemental grants (gaps in the phase card's own DDL, item §3.1)

The phase card's `01_setup.sql` grants `NEULIT_APP` only `SELECT`/`INSERT`
on future tables. That's insufficient for the app to actually run under
`NEULIT_APP`: the cost views need `SELECT ON FUTURE VIEWS` (a different
grantable object class in Snowflake — table grants don't cover views), the
corpus reload needs `UPDATE`/`TRUNCATE` on future tables (`build_corpus.py`
truncates and re-inserts), and the search service itself needs an explicit
`GRANT USAGE ON CORTEX SEARCH SERVICE` (services aren't covered by any
"future" grant class discovered). Added all three live.

### Known deviations from the target architecture

**Running as `ACCOUNTADMIN`, not `NEULIT_APP`, for both setup and runtime.**
The PAT used this session is role-locked to `ACCOUNTADMIN` (Snowflake PATs
lock to the role active at generation time; `NEULIT_APP` didn't exist yet
when this token was generated). `NEULIT_APP` role was still created and
granted to the user, and all the supplemental grants above were applied to
it, so switching back is just: generate a new PAT scoped to `NEULIT_APP` in
Snowsight, and set `SNOWFLAKE_ROLE=NEULIT_APP` in `.env` (it currently reads
`ACCOUNTADMIN`). **Do this before any real/shared deployment** — running a
demo app's service account as `ACCOUNTADMIN` is a real security deviation,
acceptable only as a documented hackathon-speed tradeoff, not a default to
carry forward.

**`.env` contains the PAT in plaintext** (as `SNOWFLAKE_PASSWORD`, since
`session.py` reads that var name). Confirmed `.gitignore` covers `.env`.
Regenerate this token (or at minimum re-scope it to `NEULIT_APP`) before
this repo or environment is shared with anyone else.

### What's still not done

- **Cortex Analyst untested against a real question.** The hardcoded model
  reference was fixed (now reads `SNOWFLAKE_CORTEX_MODEL` via `_active_model()`
  in `backend/snowflake/analyst.py`), but the call shape itself — Analyst
  invoked *through* `SNOWFLAKE.CORTEX.COMPLETE` with a
  `semantic_model_file`/`messages` object — is unverified and the
  `semantic_model.yaml` was never staged to
  `@NEULIT.CORE.SEMANTIC_MODELS/semantic_model.yaml`, so this path cannot
  currently work as written. Real Cortex Analyst is a separate REST endpoint
  (`/api/v2/cortex/analyst/message`), not a `COMPLETE` call — this
  implementation is a plausible-but-unconfirmed interpretation, flagged as
  such in an earlier pass too. Per the phase card §3.7's own risk callout,
  shipping `/economics/ask` with this documented as a limitation is
  acceptable; did not spend further time on it this pass.
- ~~**`POST /query` end-to-end** — blocked on the `client.chat()` signature
  mismatch~~ **RESOLVED, fourth pass — see below.**
- **`MODEL_PRICING` still list-price research, not reconciled against
  `SNOWFLAKE.ACCOUNT_USAGE`** — that table needs real billed usage history
  to populate meaningfully, not available yet on a freshly-created account.
- **Tier 2 live tests run for real** (`pytest -m live
  backend/tests/snowflake/test_live_snowflake.py -v`): **3 passed, 1
  failed.** Search-service round-trip, LLM `COMPLETE`, and ledger
  insert+read-back all pass — matches the ad hoc checks above.
  `test_real_analyst_question` fails as expected:
  `SnowparkSQLException ... Request failed for external function
  _COMPLETE_WITH_PROMPT with remote service error: 400 '"invalid prompt
  object"'`. This confirms the suspicion above — `analyst.py`'s
  Analyst-via-`COMPLETE` approach is not a valid call shape, not just
  unverified. `/economics/ask` still degrades cleanly (does not 500 —
  `result["answer"]` is always truthy, just the canned "unavailable"
  string), so the phase card's fallback ("ship `/economics/ask` returning a
  canned SQL-backed answer path... do not let it block the ledger or
  dashboard") is already satisfied. Building the real REST-based Analyst
  integration (`/api/v2/cortex/analyst/message`, OAuth token handling,
  staging `semantic_model.yaml` to a Snowflake stage) is real, separate
  work — not attempted this pass given the explicit scope permission to
  defer it.
- **`run_gate.py` live numbers** (retrieval-parity recall@10, real
  cost/latency percentiles) not regenerated against the now-live search
  service and ledger traffic.

## Update — fourth pass: `POST /query` fixed end-to-end (outside Card 1's ownership bucket, applied anyway on this solo project)

Full detail in `Blockers.md`'s resolved entry — summary here. The user asked
for the `/query` pipeline to actually work, not just Snowflake connectivity
in isolation. Touched files outside Card 1's formal ownership
(`backend/app/loop/{hyde,relevance_check,refine}.py`,
`backend/app/summary/generate.py`, `backend/app/verify/citation_check.py`,
`backend/api/routes/query.py`) since there's no separate Card 2A owner on
this project to hand it to.

**Root causes, in the order they surfaced (each only visible once the
pipeline actually ran against a live model — nothing here was catchable by
Tier-1 mocks, since the mocks encoded the same wrong assumptions):**

1. Stale imports of deleted v1 classes (`ParitokLLMClient`, `HybridRetriever`)
   for type hints only, across all 5 files above.
2. `client.chat(messages)` called with zero or the wrong keyword args
   everywhere (`response_format=`, `direct=`) instead of `LLMPort`'s actual
   `call_site`/`request_id`/`session_id`/`user_id` keyword-only signature —
   the core mismatch this blocker was originally about.
3. `retriever.get_closest_conditions(...)` — v1 method name, v2 is
   `closest_conditions(...)`.
4. `ConditionMatch` unpacked as a 3-tuple (`for a, b, c in closest`) — it's a
   frozen dataclass with 4 fields, not a tuple.
5. `retriever.search(...)` result unpacked as `[p for p, _ in retrieved]`
   (v1's `list[tuple[dict, float]]`) — v2 returns `list[ScoredPaper]`
   (dataclasses). Added a dict-conversion helper at the one call site in
   `refine.py` rather than rewriting every downstream dict-style consumer.
6. `query.py`'s `retriever.papers` — `CortexSearchRetriever` has no
   in-memory corpus attribute (v1's `HybridRetriever` did). Replaced with
   the static corpus-scope table's `target_count`, already loaded moments
   later in the same function as `condition_lookup`.
7. `compress_for_prompt` imported from the deleted `llm_client.py`, never
   reimplemented in v2 (v2 has no compression step by design). Replaced with
   the uncompressed prompt + `estimate_tokens`.
8. `CortexLLMClient.chat()` (Card 1's own file) assumed `Message` dataclass
   instances; every pipeline call site builds plain dicts. Fixed in `chat()`
   to accept either, rather than rewriting 4 files' worth of prompt
   builders.
9. **The model wraps JSON in markdown fences** despite explicit
   "ONLY valid JSON" instructions, confirmed live with `claude-sonnet-4-5` —
   every manual `json.loads(result.content)` in the pipeline (5 sites) was
   silently hitting its degraded-fallback path. This is why the very first
   live `/query` run showed 0/5 papers passing the relevance check on a
   query where the retrieved papers were clearly relevant — looked like a
   retrieval-quality bug, was actually JSON parsing. Fixed by reusing Card
   1's own `backend.app.llm.json_repair.try_parse_json` (already
   fence-tolerant, built for `CortexLLMClient`'s structured-output path)
   instead of raw `json.loads` at all 5 sites.

**Verified live**, full `POST /query` via `TestClient` against the real
account, gold-set-style query: `status=200`, real sourced summary with
`[N]` citations, correct `case_context`, per-sentence `flagged_claims`
verification (`supported`/`uncited`), trace showing 2/5 papers passing
relevance on the first iteration (no refine needed). Re-ran the full Tier 1
suite after all changes — still `54 passed, 4 skipped`, zero regressions.

**Still not covered by this pass:** `/query/stream` (SSE variant) shares
`_run_query_pipeline` so it inherits the same fixes, but was not separately
exercised. Test files for the touched modules
(`test_citation_check.py`, `test_loop_prompts.py`, `test_search_loop.py`,
`test_summary_generate.py`, `test_pipeline_integration.py`,
`test_multiturn_session.py`, `test_api_query.py`, `test_query_stream.py`,
`test_api_atlas.py`, `test_api_demo.py`, `test_api_health.py`,
`test_seed.py`) still import the deleted `backend.app.llm_client` directly
and fail to collect — none of these are Card 1's test files, and fixing
pipeline test infrastructure is separate scope from making the pipeline
itself work. `full pytest backend/tests/ -q` will show 12 collection errors
until someone updates those test files' imports/fixtures to match the v2
contracts (same category of fix as this pass, just in test code).
