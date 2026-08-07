# Decisions

Append-only. One entry per architecturally-significant decision made ahead
of need, so it isn't made under checkpoint pressure later. Names the
trigger, the decision, and who acts on it.

## [c1] Contingency: `claude-3-5-sonnet` unavailable in account's Cortex region

**Trigger:** plan-v2/01-PHASE-CARD-1-snowflake-platform.md section 5, item
4: "Cortex model availability is region-specific. Confirm your account's
region supports `claude-3-5-sonnet` on `COMPLETE` before building around
it." This decision is being recorded now, ahead of CP3, precisely so it does
not get made under CP3 pressure with a live account already burning
credits.

**Status:** not yet triggered in this sandbox — no live Snowflake account
was available to check region/model availability. This entry documents the
plan for whoever hits it first with real credentials.

**Decision, if `claude-3-5-sonnet` is confirmed unavailable on `COMPLETE`
in the account's region:**

1. **Check availability first, don't guess.** Run, with a live session:
   ```sql
   SELECT SYSTEM$SHOW_AVAILABLE_LLM_MODELS(); -- or the current equivalent
   -- or attempt a minimal COMPLETE call and read the error:
   SELECT SNOWFLAKE.CORTEX.COMPLETE('claude-3-5-sonnet', 'ping');
   ```
   Snowflake's error message on an unsupported model names the account's
   region and (usually) suggests supported alternatives — capture the exact
   error text into this entry before proceeding.

2. **Pick the best available substitute, in this preference order** (per
   plan-v2/00-SHARED-CONTRACTS.md section 2.2's single-provider constraint —
   no fallback chain, no second pricing model, no Groq or non-Cortex
   provider under any circumstance):
   - `claude-sonnet-4-5` if available (Anthropic's current-generation model
     on Cortex as of this research pass — see the `MODEL_PRICING` research
     note in `snowflake/sql/02_tables.sql` and `Handoff-Log.md` item 4,
     which already seeds a pricing row for this model as a hedge).
   - Otherwise, the best available Claude model on `COMPLETE` in that
     region, largest context/quality tier Snowflake exposes.
   - Only if no Claude model is available at all: the best available
     non-Claude model Cortex COMPLETE exposes in that region. This is a
     last resort, not a preference — flag it loudly in this file if it
     happens, since it changes the JSON-schema/repair-prompt assumptions
     baked into `backend/app/llm/json_repair.py` (which were tuned against
     Claude's response shape) and may need re-validation.

3. **Wire the substitution through configuration, not code.** Set
   `SNOWFLAKE_CORTEX_MODEL=<chosen-model>` in the deployment environment —
   `backend/snowflake/llm.py`'s `_active_model()` already reads this env
   var and defaults to `claude-3-5-sonnet` only when it's unset, so no code
   change is required in `CortexLLMClient`.

4. **Update `MODEL_PRICING` for the chosen model.** `INSERT`/`MERGE` a row
   into `NEULIT.CORE.MODEL_PRICING` for `<chosen-model>` with real credit
   rates from `SNOWFLAKE.ACCOUNT_USAGE` / the account's Cortex rate card
   (not list-price research numbers — see `Handoff-Log.md` item 4 on why
   the seeded rows are a starting point, not a substitute for account
   verification) before any `/economics` cost number can be trusted for
   this model. `CortexLLMClient.health()` already returns
   `{"ok": False, "detail": "model ... missing from MODEL_PRICING"}` if this
   step is skipped, so the failure mode is loud rather than a silently wrong
   $0 cost.

5. **Update `snowflake/sql/semantic_model.yaml`** if it references
   `claude-3-5-sonnet` by name anywhere in the Cortex Analyst call (it does,
   in `backend/snowflake/analyst.py`'s hardcoded
   `SNOWFLAKE.CORTEX.COMPLETE('claude-3-5-sonnet', ...)` call for the
   Analyst-over-COMPLETE path) — swap it to read `SNOWFLAKE_CORTEX_MODEL`
   the same way `llm.py` does, or hardcode the confirmed-available
   substitute, so Analyst and the main chat path never disagree about which
   model is live.

6. **Record the actual substitution here** (append, don't edit the plan
   above) once it happens: chosen model, region, the exact
   unavailability error text from step 1, and the date.

**Owner:** whoever on Card 1 (or a successor lane, if Card 1 has handed off
by then) first gets real Snowflake credentials and runs CP1/CP2 setup.

---

## [c1] Proposal: surface cache hit-rate / cost-saved on /economics/summary (needs 2A/2B sign-off)

**Context:** Phase C of the hackathon "Cost of Intelligence" feature
(prompt caching + context compression, `backend/app/llm/cache.py` +
`backend/app/llm/compress.py`) produces real, per-run numbers --
`cache_stats()` returns `{hits, misses, hit_rate, estimated_cost_saved_usd}`
-- that would be a natural addition to the demo dashboard.

**Why it's not wired in:** `GET /economics/summary`'s response shape is
frozen at contracts-v1 (`plan-v2/00-SHARED-CONTRACTS.md` section 4):

```
GET /economics/summary?window=24h
  res  { total_requests, total_tokens, total_cost_usd,
         by_call_site: {call_site, requests, tokens, cost_usd}[],
         by_hour: {hour_iso, tokens, cost_usd}[] }
```

There is no field for cache hit-rate or cost-saved, and per section 4's own
rule ("Card 2B never asks Card 2A to change a shape mid-build -- if a shape
is wrong, it is logged in Decisions.md and changed once, at an integration
checkpoint, by both at the same time"), Card 1 is not changing this shape
unilaterally. `backend/api/routes/economics.py` (Card 1 ownership) is left
untouched by this work.

**Proposed shape change** (additive, backward compatible -- existing
fields unchanged):

```
GET /economics/summary?window=24h
  res  { total_requests, total_tokens, total_cost_usd,
         by_call_site: {call_site, requests, tokens, cost_usd}[],
         by_hour: {hour_iso, tokens, cost_usd}[],
         cache: { hits: number, misses: number, hit_rate: number,
                  estimated_cost_saved_usd: number } }
```

Backed by `backend.app.llm.cache.cache_stats()`, which already returns
exactly this shape (see `backend/app/llm/cache.py`). Wiring would be a
one-line addition to `EconomicsSummaryOut` (new optional `cache` field) and
one line in `economics_summary()`'s two return statements.

**Owner:** needs Card 2A (owns `backend/api/dependencies.py` / the app
wiring, and is the other party to the section 4 HTTP contract) and Card 2B
(consumes this shape via generated `api-types.ts`) sign-off before this
lands, per the section 4 rule above. Not resolved by Card 1 in this pass.
