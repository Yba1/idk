---
title: Architecture
---

# Architecture

![NeuLitTrace component map](/diagrams/architecture.svg)

The Next.js client calls FastAPI through a generated OpenAPI contract. FastAPI orchestrates four independent ports:

| Port | Live adapter | Responsibility |
|---|---|---|
| Retrieval | Cortex Search | Hybrid literature search and condition lookup |
| LLM | Cortex COMPLETE | Six labeled inference call sites |
| Memory | EverOS | Profile, thread, seen-paper history, specialty, forget |
| Ledger | Snowflake | One priced event for every model call |

## Why the ports matter

Each dependency has its own health result and degraded path. Memory can fail without disabling retrieval, and the ledger can fail without suppressing an answer. The application footer exposes all four states.

## Request flow

![Query request flow](/diagrams/request-flow.svg)

The pipeline expands the query, searches, applies memory deduplication and re-ranking, checks relevance, optionally refines, writes the summary, verifies citations, records memory, and returns the result with cost.

## Reliability

![Independent degradation paths](/diagrams/reliability.svg)

An unpersonalized answer is labeled as such, and zero ledger data produces an explicit not-reporting state.
