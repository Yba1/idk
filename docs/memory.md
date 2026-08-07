---
title: EverMind Memory
---

# EverMind memory

![EverMind personalization loop](/diagrams/memory-loop.svg)

EverOS stores a researcher profile, a session thread, and the PMIDs already shown. The UI exposes specialty, explored conditions, counts, and distilled context verbatim.

## Namespacing

Profiles are keyed by `user_id`; threads add `session_id`. The demo trusts that user ID and has no authentication, so this is not a production tenant boundary.

## Re-ranking guardrail

Memory adjusts a paper only within `[0.6, 1.2]`. Personalization may reduce repetition or strengthen continuity, but it must never overpower the rarity signal.

## Latency and degradation

Memory has a 300 ms budget. If it is unavailable or personalization is off, retrieval continues and `memory.applied` is false. The frontend explains that state instead of implying a cold result was personalized.
