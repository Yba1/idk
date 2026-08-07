-- NeuLitTrace v2 — Card 1. Run after 01_setup.sql.
USE ROLE NEULIT_APP;
USE WAREHOUSE NEULIT_WH;
USE DATABASE NEULIT;
USE SCHEMA CORE;

CREATE OR REPLACE TABLE NEULIT.CORE.PAPERS (
  PMID        STRING       NOT NULL PRIMARY KEY,
  TITLE       STRING       NOT NULL,
  ABSTRACT    STRING       NOT NULL,
  JOURNAL     STRING,
  PUB_YEAR    NUMBER(4,0),
  CONDITION   STRING       NOT NULL,
  IS_RARE     BOOLEAN      NOT NULL,
  URL         STRING,
  SEARCH_BLOB STRING       NOT NULL,   -- TITLE || ' ' || ABSTRACT, what Cortex Search indexes
  LOADED_AT   TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
);

CREATE OR REPLACE TABLE NEULIT.CORE.CONDITIONS (
  CONDITION     STRING NOT NULL PRIMARY KEY,
  IS_RARE       BOOLEAN NOT NULL,
  PAPER_COUNT   NUMBER,
  DESCRIPTION   STRING,
  BRAIN_REGIONS ARRAY,
  CONDITION_VEC VECTOR(FLOAT, 768)     -- Cortex EMBED_TEXT_768 over DESCRIPTION
);

CREATE OR REPLACE TABLE NEULIT.CORE.TOKEN_LEDGER (
  EVENT_ID          STRING DEFAULT UUID_STRING(),
  REQUEST_ID        STRING NOT NULL,
  SESSION_ID        STRING,
  USER_ID           STRING,
  CALL_SITE         STRING NOT NULL,   -- hyde|relevance_check|refine|summary|citation_check|memory_distill
  MODEL             STRING NOT NULL,
  PROMPT_TOKENS     NUMBER NOT NULL,
  COMPLETION_TOKENS NUMBER NOT NULL,
  TOTAL_TOKENS      NUMBER NOT NULL,
  COST_USD          NUMBER(18,8) NOT NULL,
  LATENCY_MS        NUMBER,
  DEGRADED          BOOLEAN DEFAULT FALSE,
  OCCURRED_AT       TIMESTAMP_NTZ NOT NULL
);

CREATE OR REPLACE TABLE NEULIT.CORE.MODEL_PRICING (
  MODEL              STRING NOT NULL PRIMARY KEY,
  CREDITS_PER_MTOK_IN  NUMBER(18,8) NOT NULL,
  CREDITS_PER_MTOK_OUT NUMBER(18,8) NOT NULL,
  USD_PER_CREDIT       NUMBER(18,8) NOT NULL,
  EFFECTIVE_FROM     TIMESTAMP_NTZ NOT NULL
);

-- Seed MODEL_PRICING for the default model + its likely current equivalent.
--
-- Researched 2026-08-07 (WebSearch, no live Snowflake account available in
-- this sandbox to cross-check against SNOWFLAKE.ACCOUNT_USAGE). Snowflake's
-- Cortex AI pricing moved to a token-based "AI Credit" model effective
-- 2026-04-01, billed against a per-model Service Consumption Table at a
-- flat $2.00/credit list rate ($2.20 for regional/cross-region processing).
-- Published rate found for `claude-sonnet-4-5` via AI_COMPLETE:
--   1.8 credits / 1M input tokens, 9.0 credits / 1M output tokens
--   (~$3.60 per 1M input tokens, ~$18.00 per 1M output tokens at $2/credit).
-- Sources:
--   https://www.finout.io/blog/snowflake-cortex-pricing
--   https://www.finout.io/tools/snowflake-cortex-cost-calculator
--   https://www.snowflake.com/en/developers/guides/cortex-rest-api-billing-cost/
--
-- `claude-3-5-sonnet` (this app's SNOWFLAKE_CORTEX_MODEL default, see
-- backend/snowflake/llm.py) did not have a discoverable, distinctly-cited
-- current rate in this pass -- `claude-sonnet-4-5` appears to be the
-- generally-available successor Snowflake now publishes rates for, and is
-- the most defensible real-numbers proxy available without account access.
-- Both rows are seeded below so the app keeps working against either model
-- name. THIS STILL MUST BE RECONCILED against the account's actual
-- SNOWFLAKE.ACCOUNT_USAGE / Service Consumption Table once live -- list
-- prices can differ from an account's actual billed rate, and Cortex model
-- availability is region-specific (see Decisions.md and Handoff-Log.md).
-- Phase E (call-site model routing, backend/app/llm/routing.py) adds
-- `mistral-7b` as the default cheap-tier model for relevance_check/hyde.
-- PLACEHOLDER RATE, not a researched citation like the two rows above --
-- no discoverable published per-token AI Credit rate for `mistral-7b` was
-- found in this pass (WebSearch turned up Cortex COMPLETE's general
-- per-token credit-consumption model but not a model-specific rate table
-- entry for this model the way claude-sonnet-4-5's finout.io citation
-- gave). Rate below is a conservative placeholder (roughly an order of
-- magnitude cheaper than the claude-3-5-sonnet row, consistent with
-- Mistral 7B's much smaller parameter count vs. Claude 3.5 Sonnet) so
-- routing-on cost math is directionally correct and doesn't silently
-- report $0. MUST be replaced with the account's real
-- SNOWFLAKE.ACCOUNT_USAGE / Service Consumption Table rate for this model
-- before any /economics number that includes cheap-tier calls is trusted
-- for a real cost claim -- flagged in Decisions.md alongside the existing
-- claude-3-5-sonnet / claude-sonnet-4-5 reconciliation item.
MERGE INTO NEULIT.CORE.MODEL_PRICING AS tgt
USING (
  SELECT * FROM VALUES
    ('claude-3-5-sonnet', 1.8, 9.0, 2.0, CURRENT_TIMESTAMP()),
    ('claude-sonnet-4-5', 1.8, 9.0, 2.0, CURRENT_TIMESTAMP()),
    ('mistral-7b', 0.2, 0.9, 2.0, CURRENT_TIMESTAMP())  -- PLACEHOLDER, see comment above
  AS t(MODEL, CREDITS_PER_MTOK_IN, CREDITS_PER_MTOK_OUT, USD_PER_CREDIT, EFFECTIVE_FROM)
) AS src
ON tgt.MODEL = src.MODEL
WHEN NOT MATCHED THEN INSERT (MODEL, CREDITS_PER_MTOK_IN, CREDITS_PER_MTOK_OUT, USD_PER_CREDIT, EFFECTIVE_FROM)
VALUES (src.MODEL, src.CREDITS_PER_MTOK_IN, src.CREDITS_PER_MTOK_OUT, src.USD_PER_CREDIT, src.EFFECTIVE_FROM);
