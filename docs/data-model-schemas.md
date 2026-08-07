---
title: Contract Schemas
---

# Contract schemas

Frozen dataclasses and port protocols are the seam between Snowflake, EverMind, FastAPI, and the UI. The HTTP projection is generated into `frontend/src/lib/api-types.ts` from OpenAPI.

## Core records

- `Paper` and `ScoredPaper`: source metadata plus lexical, semantic, rarity, and memory scores.
- `ResearcherProfile`: specialty, explored conditions, query count, and distilled context.
- `SessionThread`: session queries and PMIDs shown.
- `TokenUsage` and `LedgerEvent`: priced usage, latency, degradation, identity, and call site.

## Query response

`QueryResponse` returns sourced markdown, citations, scored papers, trace rounds, brain region, memory effects, and per-request cost. Trace rounds include `memory_applied` and `seen_filtered`; papers expose `memoryMultiplier`.

## Contract discipline

Frontend types are never patched by hand. If regeneration breaks the build, the mismatch is logged through Obsidian and fixed at an integration checkpoint.
