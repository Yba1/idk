---
title: Search Loop
---

# Search Loop

Iterative retrieval systems face a fundamental tradeoff: a single-pass retrieval call may miss papers because the original query lacks domain-specific vocabulary (e.g., "tremor in a PET patient" vs. "hyperkinetic disorder of the basal ganglia"), but each refinement step adds computation and token usage. NeuLitTrace's self-correcting search loop solves this by running up to two iterations of HyDE-expansion, hybrid retrieval, and relevance checking, abandoning unpromising branches early to stay within token budgets while avoiding the "historical context inflation" problem common in multi-turn RAG systems.

<img src="/diagrams/search-loop.svg" alt="NeuLitTrace self-correcting search loop sequence diagram" style="width:100%; max-width:1400px; border:1px solid var(--vp-c-divider); border-radius:8px; padding:12px; background:#fff;" />

## Overview

This page documents how the search loop's iterative retrieval decision process works, what happens when it fails to find relevant papers, and the originality considerations behind its design.

## How it Works

The search loop runs up to 2 iterations, attempting to retrieve at least 2 relevant papers per iteration. On success or timeout, it returns the relevant results and a trace log entry showing every refinement step.

### 1. HyDE expansion

When a user enters a query like "rare cerebellar atrophy on neuroimaging," the loop asks the LLM to generate a short, plausible case-report abstract (3-5 sentences) matching that query. This serves a retrieval purpose only, used internally to boost recall rather than shown to users. Case-report language overlaps much better with published literature than a symptom description does, so the expanded text increases recall during hybrid search.

For iterations after the first, the prior iteration's reasoning string (e.g., "iteration 1 flagged: 1/5 papers passed relevance") is appended to the expansion prompt, so the model understands the failure mode and writes a more targeted hypothetical document.

The HyDE prompt is routed through the Paritok proxy.

### 2. Hybrid retrieval

The loop searches the corpus using both the raw query and the HyDE-expanded text, scoring each with a blend of BM25 (lexical) and vector (semantic) rankings. Each query's results are scored independently first, then merged.

For a single query, the blended score is:

$$\text{score}_q = 0.5 \cdot \text{bm25\_norm}_q + 0.5 \cdot \text{vector\_norm}_q$$

where the normalization scales each score set to [0,1] independently. If a secondary query (the HyDE expansion) is provided, the primary and secondary scores are then merged with a 60-40 split favoring the raw query:

$$\text{score} = 0.6 \cdot \text{score}_{\text{primary}} + 0.4 \cdot \text{score}_{\text{secondary}}$$

A rarity-boost multiplier is applied next. Papers marked `rarity: "rare"` are multiplied by 1.6; all others by 1.0. This ensures that rare and underexplored conditions retain retrieval prominence even when common conditions have denser literature coverage.

The top 5 papers by final score are returned.

### 3. Batched relevance check

All retrieved papers are evaluated together in a single structured LLM call. The model returns a JSON object assigning a boolean relevance flag and a confidence score (0-1) to each paper, then the loop filters the results to keep only those marked relevant.

The relevance prompt is routed through the Paritok proxy.

### 4. Pass or fail decision

An iteration passes if at least 2 papers were judged relevant. If it passes, or this was the final allowed iteration (iteration 2), the loop returns immediately with the relevant papers and trace information.

### 5. Refine and retry

If an iteration retrieved fewer than 2 relevant papers and more iterations remain, the loop constructs a short reasoning string ("iteration N flagged: X/Y papers passed relevance") and sends a refine-query prompt asking the model to revise the search query given that low-confidence result. The refined query becomes the input to the next iteration's HyDE expansion, carrying the prior reasoning forward into the new hypothetical document.

Every iteration's outcome is logged as a `LoopTraceEntry` and returned to the frontend as part of the API response, so the loop's decision path is visible on screen.

### When retrieval fails: out-of-scope detection

If both iterations complete and the loop still has zero papers (nothing passed relevance filtering), the query is out-of-scope for the corpus. Rather than spending LLM tokens on a summary for an unrelated query, the backend route calls `retriever.get_closest_conditions(query, top_n=3)` to suggest the most similar conditions the corpus does cover.

This matching uses condition-centroid embeddings ranked by cosine similarity against the query. Suggested conditions are those scoring at or above a 0.42 similarity threshold. The API returns `no_match=True` with these suggestions and skips summary generation, keeping latency and token spend minimal. See the Architecture page (`/architecture`) for the full flow, including sparse-coverage handling when retrieval does succeed.

### Originality: historical context inflation

Iterative RAG systems have a documented problem in the literature called "historical context inflation." Each refinement round can carry forward the full retrieval and reasoning history, causing cumulative input tokens to grow across turns, unlike a system that runs isolated single-turn calls that each forget the previous failure and hold roughly constant per-turn cost.

NeuLitTrace deliberately exercises this pattern. The loop's `prior_reasoning` string is appended to each iteration's HyDE prompt (step 1), so the model understands why the prior round was low-confidence and can write a more targeted hypothetical. This makes the loop a realistic instance of historical context inflation rather than a synthetic toy scenario.

The measurement gate captured real token-growth numbers from this multi-turn session in the `multiturn_session` field of `backend/measurement/results/candidate_results.json`. These numbers demonstrate why token compression (the core of Paritok's value proposition) matters for iterative RAG workloads.

## Related Documentation

- [Architecture](/architecture): how these calls route through the Paritok proxy and where the search loop sits in the full request flow
- [LLM Egress Paths](/architecture-llm-paths): retry and routing behavior for the proxy calls this loop makes
- [Paritok Integration & Measured Numbers](/paritok-integration): token-growth numbers captured from this multi-turn session
- [Data Model: API Schemas](/data-model-schemas): shape of the `LoopTraceEntry` records this loop produces
