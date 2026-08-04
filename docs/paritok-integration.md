---
title: Paritok Integration & Measured Numbers
---

# Paritok Integration & Measured Numbers

NeuLitTrace uses Paritok's compression pipeline to reduce token usage in the sourced-summary generation phase. This runs as a direct pipeline call: the sourced-summary LLM call itself goes straight to Groq (`direct=True`), and immediately before it, `compress_for_prompt()` calls Paritok's compression pipeline (`paritok.yaml`, `use_gpu_server: true`) directly on the stuffed-abstracts context. The local proxy handles a separate set of calls (HyDE, relevance-check, refine), keeping this compression step scoped to the summary path alone.

## Overview

This page reports the measurement gate results, the multi-turn session comparison, and current evaluation limitations for the Paritok integration. See [Architecture](/architecture) for the full routing detail across direct chat, search loop, and summary-generation paths.

## Measured Results

### Impact at a glance

<img src="/diagrams/paritok-usage.svg" alt="Paritok impact diagram: development and LLM request paths converging into total tokens in, tokens out, and dollars saved" style="width:100%; max-width:none; border:1px solid var(--vp-c-divider); border-radius:8px; padding:12px; background:#fff;" />

Figures are pulled from the Paritok account dashboard, covering both the Development and LLM Request paths for NeuLitTrace, and were last checked 2026-08-03; re-verify before citing.

Token savings are concentrated in one call site (the sourced-summary call, Candidate B); the search-loop calls (Candidate A) saw a reduction too small to count as a real win. Integrating the hosted GPU backend also introduced real development friction, cold-start timeouts, silent failure on the compression call, and a leaked reference tag, that a custom wrapper had to work around. Cold starts specifically are handled on both ends: an 8-second passthrough fallback on the backend, and a staged loading state on the frontend so the delay reads as expected behavior rather than a stall (see [Why Paritok](/why-paritok)).

### Measurement gate

We ran a controlled A/B test against a 15% token-reduction threshold to identify which compression surface would yield the largest savings. Two candidates were measured:

| Candidate | Tokens before | Tokens after | Reduction |
|---|---|---|---|
| A: search-loop calls (HyDE, relevance-check, refine) | 1434 | 1442 | -0.56% |
| B: sourced-summary call (compress_for_prompt on stuffed abstracts) | 4159 | 2458 | **40.9%** |

**Candidate B won** and is now in production. The 40.9% reduction clears the 15% threshold; Candidate A does not.

Candidate A shows essentially no reduction, a slight increase in token count rather than a saving. This is expected behavior: the HyDE, relevance-check, and refine prompts are short and fall below Paritok's `compression.min_tokens: 512` gate in `paritok.yaml`, so `compress_for_prompt` applies only where it can help most: the large stuffed-abstracts summary prompt. See [Search Loop](/search-loop) for the mechanics that generated the multi-turn test scenario.

### Multi-turn session

We measured token usage across a 6-turn conversation, comparing proxied (through Paritok) against direct calls to Groq's API. Both paths produced identical cumulative prompt tokens at each turn: 92, 185, 282, 376, 470, 565. At the tested six-turn conversation length, the proxied and direct paths performed identically.

## Related Documentation

- [Why Paritok](/why-paritok): the headline result (tokens in/out, dollars saved) and the narrative case for why this integration was worth building
- [Architecture](/architecture): where compression sits in the full request flow
- [LLM Egress Paths](/architecture-llm-paths): full routing detail across direct chat, search loop, and summary-generation paths
- [Search Loop](/search-loop): mechanics that generated the multi-turn measurement scenario
