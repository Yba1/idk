---
title: LLM Egress Paths
---

# LLM Egress Paths

NeuLitTrace maintains three separate, independent pathways to Groq rather than a single LLM interface, each with its own retry logic, token accounting, and failure mode. This is the most critical architectural detail behind how the pipeline stays responsive under LLM failure or latency.

<img src="/diagrams/llm-egress-paths.svg" alt="LLM egress paths diagram showing three separate routes: Path 1 via Paritok proxy, Path 2 direct to Groq, and Path 3 via Paritok GPU compression, with shared retry and Gemini fallback logic for Paths 1 and 2" style="width:100%; max-width:1400px; border:1px solid var(--vp-c-divider); border-radius:8px; padding:12px; background:#fff;" />

## Overview

Each path exists for a different reason: Path 1 is used for exploration and filtering, where a failure just means falling back to less refined retrieval. Path 2 produces the final user-facing output, so freshness matters more than routing through shared middleware. Path 3 is a token-savings optimization that stays responsive to the user, so it skips retries and degrades straight to passthrough on timeout. Keeping them separate means changes to one, such as Paritok proxy rate limits, stay isolated from the others.

## Gemini Fallback

Paths 1 and 2 include an optional Gemini API fallback: if all 3 retry attempts against the primary provider (Groq) fail and a Gemini API key is configured in the environment, the client makes one additional attempt against Google's Gemini API. This fallback was added only after Paritok's compression pipeline gained support for routing Gemini-keyed requests through the same token-optimization pipeline used for Groq calls. Previously, Gemini requests fell outside the compression pipeline entirely, making them incompatible with the token-savings strategy that all LLM calls in this application are built around. Now that Gemini can be transparently optimized alongside Groq calls, it became practical to use it as a fallback provider, ensuring that when Groq is unavailable, the application still benefits from compression and cost tracking through the same unified pipeline.

## The three paths

### Path 1: Proxy (search loop only)

**Route:** Frontend request → Backend → Local Paritok proxy (127.0.0.1:8080) → Groq API

**Used for:**
- HyDE query expansion
- Batched relevance check (evaluating top 5 papers against the query)
- Query refinement if iteration 1 fails

**Client:** `ParitokLLMClient._proxy_client`, an OpenAI SDK client pointed at `OPENAI_BASE_URL` (the local Paritok proxy address)

**Call signature:** `client.chat(..., direct=False)` (the default)

**Why separate:** The proxy can apply Paritok token-savings middleware and rate-limiting across all frontend queries. These are lower-stakes calls (they inform retrieval, not the final output) and benefit from early exit if the proxy is overloaded.

**Reliability:** Retries up to 3 times with exponential backoff (2^attempt seconds); when a Gemini API key is configured, attempts Gemini API (gemini-flash-latest) as a fallback if all primary retries fail; returns `degraded=True` on complete failure, allowing downstream code to skip refinement and use iteration 1 results even if they were marginal.

### Path 2: Direct-to-Groq (summary, citations, differential)

**Route:** Backend → Groq API (https://api.groq.com/openai/v1)

**Used for:**
- Sourced summary generation (highest stakes; this is the user-facing output)
- Citation check (verify inline citations match papers)
- Differential diagnosis check (catch overconfident claims)

**Client:** `ParitokLLMClient._direct_client`, an OpenAI SDK client pointed straight at Groq's endpoint, bypassing the Paritok proxy

**Call signature:** `client.chat(..., direct=True)`

**Why separate:** These calls produce user-facing output and require maximum freshness and token availability. Bypassing the local proxy keeps the final answer free of upstream queuing or rate-limiting delays, so summary generation continues even if the proxy is having issues.

**Reliability:** Same retry logic (3 retries, exponential backoff); when a Gemini API key is configured, attempts Gemini API (gemini-flash-latest) as a fallback if all primary retries fail; returns `degraded=True` on complete failure. Frontend falls back to showing the retrieved papers and trace when this path fails.

### Path 3: Compression pipeline (token savings only)

**Route:** Backend → Paritok compression backend (GPU-accelerated)

**Used for:**
- Compressing concatenated paper abstracts before they are stuffed into the summary generation prompt

**Client:** Direct Paritok `CompressionPipeline` object (not OpenAI-shaped)

**Call signature:** `compress_for_prompt(content, query)`, backgrounded in a thread against a module-level 8-second deadline (`COMPRESSION_DEADLINE_S`)

**Why separate:** This is the only call that actually touches Paritok's GPU compression backend for token savings. It runs in a background thread with an 8-second deadline; if the Paritok GPU is cold or overloaded, the function degrades gracefully to passthrough (returns uncompressed text), keeping the user's request moving.

**Reliability:** A single 8-second timeout leads straight to passthrough, by design: waiting for a retry would delay summary generation more than sending the larger uncompressed prompt to Groq.

**When compression succeeds:** the stuffed-abstracts block sent to Groq is smaller. See the Paritok Integration page (`/paritok-integration`) for the exact measured reduction from the project's committed measurement gate.

**When compression times out (or the Paritok GPU backend is offline):** abstracts go to Groq uncompressed. Summary quality is unchanged; only token consumption increases, which is acceptable for maintaining responsiveness.

## Related Documentation

- [Architecture](/architecture): where these three paths sit in the overall request flow, deployment, and security model
- [Paritok Integration & Measured Numbers](/paritok-integration): measured token-savings numbers from Path 3's compression pipeline
- [Search Loop](/search-loop): the retrieval logic behind Path 1's HyDE expansion and relevance check calls
