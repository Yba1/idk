---
title: Hackathon Feedback
---

# Hackathon Feedback

This page collects feedback on Paritok itself, observed while integrating it into NeuLitTrace, a non-agentic RAG application. It is written for Paritok's Most Valuable Feedback bonus prize, not as user-facing product documentation for NeuLitTrace.

## Overview

NeuLitTrace retrieves PubMed case reports and summarizes them with Groq `llama-3.3-70b-versatile` via the OpenAI-compatible proxy. It is not an agentic coding tool: each call is a single-shot system+user completion, with no tool-calling. That shape surfaced a set of integration gaps that would not show up in Paritok's primary agentic-coding-tool use case. Each item below states the observation, its effect on our development process, and a recommendation.

## What worked well

- The hosted GPU compression performs strongly once reached. It cut tokens by 54% on average across a 14-query real-corpus batch. Individual queries reached 80-95% on sparse or repetitive content. The quality is real.
- The degrade-to-passthrough design never breaks the caller's turn over a compression hiccup. This is a sound engineering call for production safety, though it would benefit from better visibility, detailed below.
- `CompressionPipeline` is a directly-callable SDK primitive, not just a proxy feature. This let us resolve our own integration gap in about 30 minutes once we understood the pattern.

## Observations from development

### 1. Single-shot RAG prompts do not qualify for compression

**Observation:** The proxy only auto-compresses `role: "tool"` messages and history above the `context_threshold`. A single-shot RAG prompt has only `system` and `user` messages. Retrieved documents sit inside the `user` message, so this shape never becomes eligible. The README states that Paritok is less useful for single-turn Q&A. That scope is documented, but no per-request signal confirms that a specific call fell outside it.

**Impact on development:** Every diagnostic signal looked correct: the health check was green, the API key was valid, the config was correct. The dashboard still showed 0 requests. We traced this to the eligibility gap. Nothing in the response distinguishes "ineligible" from "eligible but nothing to compress."

**Recommendation:** Log or flag "eligible content: none" per request. This turns a documented scope limit into a debuggable one, saving the same investigation time for the next non-agentic caller.

### 2. Cold-start latency can exceed the default timeout, with no retry path

**Observation:** RunPod serverless cold starts regularly exceed the default `gpu_server.timeout` of 90.0 seconds. We measured a successful call at 45.5s, after two consecutive timeouts on identical content. `GpuServerStrategy.compress()` has no retry or backoff, so a single cold start ends that call's compression attempt for good.

**Impact on development:** RunPod serverless is the documented hosted backend, so cold starts happen routinely, not as an edge case. The first request after any idle period still falls back to passthrough silently.

**Recommendation:** Use a longer default timeout, add an optional warm-up ping, or add a retry with backoff for this backend.

### 3. Failed compression looks identical to "nothing needed compressing"

**Observation:** A timed-out call and genuinely uncompressible content both return the original text with `ratio: 0.0`. No error reaches the caller. Only a `logger.warning` is written, and it is easy to miss without logging explicitly configured.

**Impact on development:** We could not tell, from the application side, whether compression was unnecessary or had failed. What should have been a quick check turned into a longer diagnostic effort.

**Recommendation:** Add a `degraded` or `gpu_unavailable` flag on `CompressionResult`. The reason codes already exist internally, such as `below_min_tokens` and `below_refusal_threshold`; adding `gpu_timeout` and `gpu_unreachable` would extend this naturally.

### 4. Groq models are absent from the pricing table

**Observation:** `paritok/proxy/pricing.py` has no Groq entries in its per-model $/token table. Any Groq model, including `llama-3.3-70b-versatile`, falls back to `DEFAULT_USD_PER_MTOK = 3.0`, Claude Sonnet's rate, roughly 5x Groq's real $0.59/M input price. Groq is also named as a supported OpenAI-compatible provider in the project's own documentation, so this is a gap between stated support and priced support, not an unsupported edge case.

**Impact on development:** The local `/stats` cost estimate can be inaccurate when Paritok is used for both LLM requests and Claude Code development. Dashboard figures for other Groq users are likely affected the same way, with no indication that a fallback rate was used.

**Recommendation:** Add Groq pricing to align cost reporting with the proxy's stated support for any OpenAI-compatible endpoint. Since the model weights and proxy are open source, we would be glad to submit a small PR adding the Groq entry ($0.59/M input) ourselves if that is welcome.

### 5. A `[REF:<hash>]` marker surfaces in model-visible text

**Observation:** `CompressionPipeline.compress()` prepends a literal `[REF:<hash>]` marker to the compressed text it returns. This marker travels into the prompt sent to the model, not just internal metadata. We reproduced this directly: a 3695-character block (795 tokens) compressed to 152 tokens, returned as `[REF:3d8ab3c883c4f80c] Progressive supranuclear palsy (PSP) is the most prevalent form...`. The marker is designed to work with the `expand_context` virtual tool, so an agentic caller can resolve it back to the original text on demand. Our RAG app makes single-shot completions with no tool-calling, so `expand_context` is never registered, and the marker has no resolution path.

**Impact on development:** `compress_for_prompt`'s contract is simple: callers can insert the result straight into a user message. There is no natural point to strip the marker first, since it reads as content, not a delimiter. The model echoed `[REF:dbef56f1ff0a58be]` directly into our RAG summary's reference list, affecting the exact text our citation-verification feature depends on.

**Recommendation:** Exclude the marker from the compressed text and attach it as separate metadata on `CompressionResult`. Alternatively, have `compress_for_prompt` auto-strip the `[REF:...]` prefix when no `expand_context` tool is registered in the caller's context, since that signal reliably marks a non-agentic caller with no way to resolve it.

### 6. No caller-facing deadline shorter than the configured timeout

**Observation:** `GpuServerStrategy.compress()` blocks the full `httpx.post` call for up to `gpu_server.timeout`, 180s in our config. There is no parameter to request a shorter bound for latency-sensitive callers.

**Impact on development:** We wrote our own bounded wait around `compress_for_prompt`, using `threading.Thread` with `join(timeout=8.0)` in `backend/app/llm_client.py`, to keep our request latency predictable. This works, but every latency-sensitive caller has to reimplement the same wrapper.

**Recommendation:** Add a `deadline_s` parameter to `CompressionPipeline.compress()` and `GpuServerStrategy.compress()`, degrading to passthrough on expiry, independent of the configured HTTP timeout.

## Additional gaps worth noting

- **Per-request visibility into why compression did not trigger.** Skip reasons already exist internally, such as `below_min_tokens` and `below_refusal_threshold`. Today they surface only through `trace.enabled` and a local JSONL file, which assumes local file access and manual log parsing. This suits self-hosted debugging, but does not fit a team running the hosted GPU endpoint from a managed environment. Exposing the same reasons as a count-by-reason breakdown on `/stats` would close this gap, giving hosted-endpoint users the same diagnostic depth that self-hosted trace users already have.

- **Documentation for non-agentic and RAG workloads.** The current docs and proxy design center on agentic coding-tool traffic: `tool_result` blocks, growing conversation history, virtual tools such as `expand_context`. The README states that Paritok is less useful for single-turn Q&A. That line is accurate, but it stops short of guidance for that case. A short section on calling `CompressionPipeline` directly would help, since this is the path that actually fits single-shot RAG and chat workloads. The same section could note that the `[REF:...]` marker depends on `expand_context`, so non-agentic callers know upfront that the marker has no built-in resolution path outside the agentic loop.

- **Contribution path for provider pricing entries.** `pricing.py` lives in an open-source, Apache-2.0 licensed repository. Neither the README nor the repository's contribution guidelines describe a process for adding a new provider's pricing. A short note on this would help any team using an OpenAI-compatible provider outside the current table, not just Groq, contribute their own entry with confidence.

## Related Documentation

- [Why Paritok](/why-paritok): the case for integrating Paritok, and the measured result.
- [Paritok Integration & Measured Numbers](/paritok-integration): the measurement gate, multi-turn comparison, and routing detail this feedback is grounded in.
- [Architecture](/architecture): the full routing detail across direct chat, search loop, and summary-generation paths.
