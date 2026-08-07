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
