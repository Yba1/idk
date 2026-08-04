---
title: Why Paritok
---

# Why Paritok

NeuLitTrace was built for Paritok's Token-Efficiency Hackathon, and Paritok is not a bolted-on integration here: it sits directly on the pipeline's most expensive step, the sourced-summary call that reads every retrieved abstract at once.

## Overview

A RAG pipeline over case reports has one obvious cost center: the moment it stuffs several retrieved abstracts into a single prompt so the model can synthesize a cited answer. That prompt is large, repetitive across similar papers, and paid for on every query. This page explains what Paritok's compression pipeline does at that exact point, what it measurably saved, and what made it straightforward to integrate as an SDK primitive rather than only as a proxy.

## What it does for this pipeline

`compress_for_prompt()` in `backend/app/llm_client.py` calls Paritok's `CompressionPipeline` directly on the stuffed-abstracts context immediately before the sourced-summary call in `backend/app/summary/generate.py`, passing `upstream_model="llama-3.3-70b-versatile"` so the hosted GPU server can attribute savings at Groq's real per-model rate rather than an unlabeled default.

This is a deliberate design choice, not the default proxy path. Paritok's OpenAI-compatible proxy auto-detects and compresses `role: "tool"` content and long conversation history, the shape an agentic coding tool produces. A single-shot `system` + `user` RAG prompt with a large context block stuffed into `user` never enters that auto-detection. Calling `CompressionPipeline` directly on the stuffed-abstracts block is what actually reaches the Paritok GPU server for this pipeline's call shape, and finding that distinction is what let this integration work at all: see [Paritok Integration & Measured Numbers](/paritok-integration) for how the measurement gate confirmed which call site was worth compressing.

## What worked well

**The measured savings are real, not marginal.** The winning candidate, the sourced-summary call, reduced 4159 tokens to 2458, a 40.9% cut, comfortably clearing the 15% threshold set for this gate. On a 14-query real-corpus batch measured separately, individual queries reached 80 to 95% reduction on sparse or repetitive content, averaging 54%. That range shows the compression is doing real work on real case-report text, not just shaving a fixed overhead.

**`CompressionPipeline` as a directly-callable SDK primitive is what made the fix possible.** Once the proxy's message-shape limitation was understood, calling the pipeline directly on the stuffed-abstracts string, instead of only through the proxy, took about 30 minutes to wire in. Exposing the pipeline as its own importable class, not only as proxy middleware, is exactly the surface a RAG app needs.

**The degrade-to-passthrough design is the right call for a production path.** `compress_for_prompt()` is written to be safe to call unconditionally: content below `compression.min_tokens` (512, set in `paritok.yaml`) or a compression call that hasn't returned yet both fall back to the original content, never blocking or failing the caller's turn. `backend/app/llm_client.py` wraps the call in an 8-second `threading.Thread` join specifically so a cold GPU backend degrades to passthrough well before the query's own latency budget is spent, and that fallback behavior is what makes it safe to call on every summary request without a feature flag around it.

**Switching backends is a one-line config change.** `paritok.yaml`'s `use_gpu_server` flag is the only thing separating a hosted Paritok GPU server call from a fully local, self-hosted model via Ollama. Nothing in the application code depends on which backend is active.

**The documented cold-start risk was designed for on both ends, not just tolerated.** `paritok.yaml` itself notes that RunPod serverless cold starts have been observed to take 45 seconds or more. On the backend, that risk is already covered by the 8-second passthrough fallback described above. On the frontend, `frontend/src/components/waking-loader.tsx` adds a second layer: the moment a query is submitted and before the first progress event arrives, it shows a staged loading state cycling through explicit phase messages, so a slow first response reads as expected behavior instead of a stalled or broken app. The two layers cover different things: the backend fallback keeps the request from blocking on a cold GPU, and the frontend loader keeps the user informed while any part of the round trip, cold GPU included, is still warming up.

## Where the current numbers stand

The 40.9% figure above is the controlled measurement-gate result: a fixed-sample A/B comparison run specifically to decide which call site to compress. Real end-to-end pipeline runs over the 7-query gold set have shown a wider spread, 26.38% to 60.26% across three dated runs, because each run regenerates retrieval and re-stuffs a different set of abstracts rather than replaying the same fixed sample. The gate decision and the real-pipeline spread are reported together, not averaged into one headline number, in [Paritok Integration & Measured Numbers](/paritok-integration), so the reported savings stay traceable to the measurement that produced them.

## Related Documentation

- [Paritok Integration & Measured Numbers](/paritok-integration): the measurement gate, real-pipeline token spread, current evaluation limitations, and the development-vs-token-efficiency impact diagram
- [Architecture](/architecture): where the compression call sits in the full request flow, alongside the two other Groq egress paths
- [LLM Egress Paths](/architecture-llm-paths): the proxy path, direct path, and compression call as three separate pathways with distinct failure modes
