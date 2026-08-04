---
title: Architecture
aside: false
---

# Architecture

NeuLitTrace is structured as a frontend and backend system communicating over HTTP, with a core retrieval-augmented generation (RAG) pipeline that performs hybrid search, relevance filtering, and synthesis.

<img src="/diagrams/architecture.svg" alt="NeuLitTrace system architecture diagram" style="width:100%; max-width:none; border:1px solid var(--vp-c-divider); border-radius:8px; padding:12px; background:#fff;" />

## Overview

The architecture emphasizes local computation for retrieval and indexing, three separate pathways for LLM calls with distinct failure modes and token budgets, and graceful degradation when any component becomes unavailable. This page documents the system's components and technology stack, the request flow from submission to response, the three LLM egress paths, and the reliability, deployment, and security behavior around them.

## How it Works

### Core components

Grouped by architectural layer rather than by request flow, this view shows what each part of the system is responsible for: presentation, API, retrieval and pipeline orchestration, external LLM services, data storage, and documentation tooling.

<img src="/diagrams/core-components.svg" alt="NeuLitTrace core components grouped by architectural layer" style="width:100%; max-width:none; border:1px solid var(--vp-c-divider); border-radius:8px; padding:12px; background:#fff;" />

### Request flow

When a user submits a query from the frontend, the request travels through the following stages:

**Frontend → API:** The client sends the query text to the backend via `POST /query` or `POST /query/stream`. The typed fetch client (`frontend/src/lib/api.ts`) attaches a 170-second timeout on both routes to accommodate Paritok GPU cold starts and the full pipeline latency.

**Search loop:** Once the backend receives the query, `run_search_loop()` (in `backend/app/loop/refine.py`) begins. This runs up to two iterations:
1. Expand the query using HyDE (Hypothetical Document Embeddings) via the proxy path to Groq
2. Perform hybrid retrieval: BM25 + vector search (both local) over the 329-paper corpus, weighted 0.6 toward the raw query and 0.4 toward the HyDE-expanded text
3. Apply a rarity-boost multiplier to papers from rare conditions
4. Retrieve the top 5 papers and run a batched relevance check via the proxy path to assess how many actually address the query
5. If fewer than 2 papers pass relevance, repeat the loop with a refined query; otherwise proceed

**Out-of-scope detection:** If the search loop returns zero papers after both iterations (nothing survived relevance filtering), the route immediately calls `retriever.get_closest_conditions(query, top_n=3)` to identify the most similar conditions in the corpus. This uses condition-centroid embeddings (the mean embedding of all papers for each condition, unit-normalized) ranked by cosine similarity against the query. Conditions scoring at or above 0.42 are returned as `suggested_conditions`. The response short-circuits with `no_match=True`, skipping summary generation and further LLM calls to keep latency and token spend minimal for unrelated queries.

**Summary generation:** Once 2 or more papers pass relevance, their abstracts are concatenated, compressed via the compression pipeline (with an 8-second timeout and automatic passthrough if the backend is cold), and sent to Groq via the direct path for summary synthesis. The LLM generates a sourced summary that cites each paper by ID. Before sending, the route computes `corpus_paper_count` across the full corpus for the best-matching condition. If fewer than 10 papers exist in the corpus for that condition, `sparse_coverage=True` is passed to the summary generator.

**Sparse-coverage disclaimer:** In `backend/app/summary/generate.py`, when `sparse_coverage=True`, a disclaimer note about limited case coverage is prepended to the summary instead of the standard low-confidence disclaimer. The sparse-coverage disclaimer takes priority when both `sparse_coverage` and `low_confidence` are true, ensuring users understand when findings are based on a small evidence base.

**Citation and differential verification:** If the Groq summary call degrades (`summary.degraded=True`), verification is skipped entirely and the response returns immediately. Otherwise, citation and differential checks run as background threads via the direct path:
- Citation check: for each `[N]`-marked claim in the summary, an LLM call judges whether the cited paper's abstract actually supports that claim, flagging unsupported, uncited, or invalid-marker claims
- Differential check: for each candidate alternate condition the model proposed, an LLM call verifies whether the cited abstract genuinely supports it as a plausible differential diagnosis. The differential check thread only starts if at least one candidate survives filtering for self-referential matches (candidates that merely restate the best-matching condition by name overlap are dropped first)

**Response:** The frontend stream receives live updates for each pipeline stage, renders a progress timeline, then displays the final sourced summary, citations, papers, and brain region visualization once all steps complete.

<img src="/diagrams/request-flow.svg" alt="NeuLitTrace request flow diagram showing the full pipeline from API route through the search loop, out-of-scope detection, summary generation, and background verification" style="width:100%; max-width:1400px; border:1px solid var(--vp-c-divider); border-radius:8px; padding:12px; background:#fff;" />

### Reliability

Every Groq and Paritok call is wrapped in `ParitokLLMClient.chat()`, which:

- Catches `APIError` and `APITimeoutError` exceptions
- Retries up to 3 times, sleeping `2^attempt` seconds between attempts (1 second, then 2 seconds) before giving up
- Always returns a structured `ChatResult`, setting `degraded=True` if all retries fail, so callers get a predictable object instead of a raised exception
- Logs all API calls, retry attempts, and final status to structured output

Downstream code always has a defined fallback path. The search loop returns whichever iteration's relevance-filtered papers are available once it reaches its iteration limit (even if marginal), or refines the query and retries first; if no papers survive filtering after both iterations, the route falls through to out-of-scope detection instead of showing marginal results. If summary generation fails, the frontend displays the papers and trace without a summary. If citation checking fails, the summary is shown with a note that verification was unavailable. This keeps the response usable even when a component fails, showing a degraded-state message in place of a raw stack trace.

**Timeouts:**
- Proxy calls and direct Groq calls: an explicit 15-second per-request timeout on both OpenAI SDK clients (`backend/app/llm_client.py`), set deliberately below the SDK's 600-second default so retry attempts stay fast even when a connection hangs
- Compression pipeline: 8 seconds, with automatic passthrough on timeout
- Frontend timeout on `/query` and `/query/stream`: 170 seconds

**Rate limiting:**
- `/query` and `/query/stream`: 10 requests per minute per client IP
- `/atlas`: 20 requests per minute per client IP

<img src="/diagrams/reliability.svg" alt="NeuLitTrace reliability flow showing retry logic, exponential backoff, and Gemini fallback" style="width:100%; max-width:900px; border:1px solid var(--vp-c-divider); border-radius:8px; padding:12px; background:#fff;" />

## Deployment

NeuLitTrace currently runs as a local development deployment: the Next.js dev server on port 3000 and FastAPI/uvicorn on port 8000. The corpus loads from a JSON file on disk into memory at backend startup, keeping the deployment footprint to two local processes. The backend reaches Groq two ways (direct, and through the local Paritok proxy) and reaches the Paritok GPU compression backend separately, both over the network. Containerization and cloud hosting are planned for a later pass.

<img src="/diagrams/deployment.svg" alt="NeuLitTrace deployment topology, local development only" style="width:100%; max-width:900px; border:1px solid var(--vp-c-divider); border-radius:8px; padding:12px; background:#fff;" />

## Security

Every request passes through four layers before reaching the query pipeline: an origin check (CORS, restricted to the configured frontend origin and to GET/POST), rate limiting (slowapi, keyed by client IP), request validation (Pydantic schemas at the request body boundary), and secrets handling (the `.env` file is loaded once at process startup, before any LLM client is constructed, keeping API keys out of the per-request code path).

<img src="/diagrams/security.svg" alt="NeuLitTrace request security layers: CORS, rate limiting, validation, secrets" style="width:100%; max-width:700px; border:1px solid var(--vp-c-divider); border-radius:8px; padding:12px; background:#fff;" />

## Technology Stack

Next.js (App Router), React, and Tailwind CSS 4 with shadcn/ui components make up the presentation layer. FastAPI, Pydantic, and slowapi handle the API layer. Retrieval runs entirely on local computation: rank-bm25 for lexical search, sentence-transformers for vector search, and nilearn for brain atlas lookups. The primary external service is Groq, routed through the Paritok proxy and GPU compression backend for token optimization. Paritok's compression pipeline now supports routing content bound for Google Gemini, so when a Gemini API key is configured, the system can use Gemini (model gemini-flash-latest) as an automatic fallback provider if the Groq pathway is unavailable; this fallback participates in the same token compression and optimization as the primary Groq calls. The corpus is a flat JSON file loaded into memory at startup for fast, dependency-free lookups.

<img src="/diagrams/tech-stack.svg" alt="NeuLitTrace technology stack bubble map, hub connected to each technology category" style="width:100%; max-width:none; border:1px solid var(--vp-c-divider); border-radius:8px; padding:12px; background:#fff;" />

## Related Documentation

- [LLM Egress Paths](/architecture-llm-paths): the three separate Groq pathways, their routing, and why they're kept independent
- [Search Loop](/search-loop): internal mechanics of HyDE expansion, hybrid retrieval weighting, and relevance filtering
- [Why Paritok](/why-paritok): what Paritok's compression pipeline does for this project and why it was worth integrating
- [Paritok Integration & Measured Numbers](/paritok-integration): measured token-savings numbers from compression and proxy middleware
- [Data Model: API Schemas](/data-model-schemas): record types that flow through the pipeline stages described above
