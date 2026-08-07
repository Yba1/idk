---
title: Corpus Data Model
---

# Snowflake corpus model

![Corpus and ledger data model](/diagrams/data-model.svg)

The live corpus is stored in Snowflake under `NEULIT.CORE`. `PAPERS` holds PubMed literature and retrieval fields; `CONDITIONS` holds rarity and anatomical metadata.

## Tables

`PAPERS` stores `PMID`, `TITLE`, `ABSTRACT`, `JOURNAL`, `PUB_YEAR`, `CONDITION`, `IS_RARE`, `URL`, the indexed `SEARCH_BLOB`, and `LOADED_AT`.

`CONDITIONS` stores `CONDITION`, `IS_RARE`, `PAPER_COUNT`, `DESCRIPTION`, `BRAIN_REGIONS`, and a 768-dimensional `CONDITION_VEC` generated from the description.

`TOKEN_LEDGER` records request, session, user, call site, model, prompt/completion/total tokens, USD cost, latency, degradation state, and occurrence time for every inference event. `MODEL_PRICING` versions the input/output credit rates and USD-per-credit conversion used when each event is written.

Card 1 verified the live account contains 329 papers across 14 conditions, 10 rare. `PAPERS_SEARCH` reported both indexing and serving active over all 329 source rows.

Cortex Search retrieves candidates; application re-ranking applies rarity and bounded memory after retrieval.
