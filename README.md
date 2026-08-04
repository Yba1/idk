# NeuLitTrace

**A search tool for rare PET and neuroimaging findings that cites every claim it makes.**

Type in a plain-language description of an imaging finding (a brain region plus an abnormality), and NeuLitTrace searches a curated set of published case reports and papers, writes a summary that answers your question, and attaches a numbered citation to every sentence so you can check the source yourself.

Built for [Paritok's Token-Efficiency Hackathon](https://github.com/Paritok-official/paritok-4b-v1).

[![Built with Paritok](https://img.shields.io/badge/Built%20with-Paritok-1f2d3d)](https://github.com/Paritok-official/paritok-4b-v1)

<img src="docs/public/screenshots/04-results-full.png" alt="NeuLitTrace sourced summary with brain region highlight and numbered citations" width="900" />

## Table of Contents

- [What problem this solves](#what-problem-this-solves)
- [Who this is for](#who-this-is-for)
- [What it is not](#what-it-is-not)
- [How it works](#how-it-works)
- [Paritok integration](#paritok-integration)
- [Tech stack](#tech-stack)
- [Project structure](#project-structure)
- [Setup and quickstart](#setup-and-quickstart)
- [Testing and measurement](#testing-and-measurement)
- [Known limitations](#known-limitations)
- [Full documentation](#full-documentation)
- [License](#license)

## What problem this solves

Search engines are good at common cases. If a symptom is well documented, a doctor or researcher can find matching literature in seconds. But rare conditions break this: there may be only a handful of published case reports on a given rare finding, and standard search or general-purpose retrieval tools have no reason to surface them over more common, better-represented conditions.

A published pilot study at Seoul National University Hospital tested nearly this exact approach (retrieval-augmented generation over PET case reports). On common cases it worked well: 84.2% of routine cases retrieved relevant matches, agreed upon by three physician readers. On rare cases it broke down. It failed to retrieve a documented case of scalp angiosarcoma specifically because the condition was rare. The authors named better rare-case retrieval as necessary future work. That is the exact gap this project targets: retrieval built to favor rare and underexplored conditions instead of penalizing them.

See [`plan/problem_and_research.md`](plan/problem_and_research.md) for the full research writeup and competitive landscape.

## Who this is for

Researchers, clinicians, and students exploring rare neuroimaging findings who want a starting point grounded in real published literature, not a general-purpose search engine or an unsourced chatbot answer. Every claim in the output traces back to a specific paper, so it is meant to be a research aid you can verify, not a final answer.

## What it is not

NeuLitTrace is a research tool, not a clinical or diagnostic tool. It does not analyze images, and it does not tell you what a patient has. The brain-region visualization shows where the literature describes findings for a matched condition, not a diagnosis generated from your input. Every summary includes a disclaimer stating this. The corpus is fixed at 329 papers across 14 conditions (10 rare, 4 common for comparison); it is not fetched live per query, so results are limited to what is in this dataset.

## How it works

**1. You describe a finding.** For example, "asymmetric parietal hypometabolism on FDG-PET with progressive apraxia" (mention a scan type, a symptom, and a brain region for the best match).

**2. The system searches and refines.** The query is expanded using HyDE (Hypothetical Document Embeddings), then matched against the corpus using hybrid search: BM25 keyword matching combined with vector similarity, with a boost applied toward rare conditions. An LLM checks whether the results are actually relevant. If not enough of them are, the system rewrites the query and searches again, up to two rounds total.

**3. The system writes a sourced summary.** Once enough relevant papers are found, an LLM reads their abstracts and writes an answer, with a `[1]`, `[2]`, etc. citation on every claim. A second LLM pass independently checks each citation against its source abstract before the summary is shown to you, flagging anything unsupported.

**4. You see the evidence, not just the answer.** The result includes an interactive brain-surface map highlighting the matched region, the full sourced summary, every cited paper, and a step-by-step trace of the search loop (each round's confidence score and whether it passed the relevance check).

For the full technical breakdown (components, request flow, reliability, and security behavior), see [`docs/architecture.md`](docs/architecture.md), or the same page rendered in the VitePress docs site (see [Full documentation](#full-documentation) below).

## Paritok integration

Paritok has saved 340.82M tokens (88.3% of the 385.86M input tokens processed across 5.6K requests during development and testing), worth an estimated $107.25. Beyond the savings, `CompressionPipeline` is exposed as a directly-callable SDK primitive rather than only a proxy side-effect, which is what made it possible to target this single-shot RAG prompt in the first place, it falls back to passthrough instead of blocking when content is too small or the compression call hasn't returned, and switching between the hosted GPU backend and a local backend is a one-line change in `paritok.yaml`. The most expensive step in this pipeline is the moment several retrieved abstracts get stuffed into one prompt so the model can write a cited summary. That is exactly where Paritok's compression pipeline is used: `compress_for_prompt()` in [`backend/app/llm_client.py`](backend/app/llm_client.py) calls Paritok's `CompressionPipeline` directly on that stuffed-abstracts context immediately before the summary call in [`backend/app/summary/generate.py`](backend/app/summary/generate.py). The local proxy handles a separate set of calls (HyDE, relevance-check, refine); this compression step is scoped to the summary path alone.

A controlled A/B measurement gate compared two candidate call sites against a 15% token-reduction threshold: search-loop calls (Candidate A) saw a negligible -0.56% change since those prompts fall below Paritok's `compression.min_tokens: 512` gate, while the sourced-summary call (Candidate B) achieved **40.9% token reduction**. Candidate B won and is in production, and a 6-turn multi-turn session showed identical cumulative token counts for proxied vs. direct calls.

The compression call is designed to be safe to call on every request: content below the minimum token count, or a compression call that has not returned yet, both fall back to the original, uncompressed text rather than blocking or failing the request.

**Cold-start UX.** Paritok's hosted GPU backend documents RunPod serverless cold starts of 45 seconds or more (`gpu_server.timeout` in [`paritok.yaml`](paritok.yaml)). Instead of letting that read as a stall, the frontend shows a staged loading state ([`waking-loader.tsx`](frontend/src/components/waking-loader.tsx)) the moment a query is submitted and before the first progress event arrives, cycling through explicit phase messages so a slow first response reads as expected behavior rather than a broken app.

Read the full story, including what worked well and the numbers behind it, in:

- [`docs/why-paritok.md`](docs/why-paritok.md), the narrative case for why this integration was worth building
- [`docs/paritok-integration.md`](docs/paritok-integration.md), the measurement gate results and current evaluation limitations
- [`plan/paritok-feedback.md`](plan/paritok-feedback.md), real friction points found in Paritok itself while building this, submitted for the Most Valuable Feedback bonus prize

## Tech stack

**Backend:** Python, FastAPI, Pydantic, slowapi (rate limiting). Retrieval runs entirely on local computation: `rank-bm25` for keyword search, `sentence-transformers` for vector search, `nilearn` for brain atlas lookups. No database; the corpus is a JSON file loaded into memory at startup.

**Frontend:** Next.js (App Router), React, Tailwind CSS 4, shadcn/ui.

**LLM and compression:** Groq's `llama-3.3-70b-versatile`, reached either directly or through a local Paritok proxy, with Paritok's `CompressionPipeline` (package `paritok==1.2.6`) compressing the summary-generation prompt.

**Docs:** VitePress, with D2-generated architecture diagrams.

## Project structure

```
backend/    Python RAG pipeline: retrieval, search loop, summary generation, API routes, tests
frontend/   Next.js app: query form, brain viewer, sourced summary and citation UI
docs/       VitePress documentation site (this README links out to it for full depth)
plan/       Problem research, build plan, and Paritok feedback log
paritok.yaml  Paritok proxy and compression configuration
```

## Setup and quickstart

### 1. Backend

Create a `.env` file in the repository root with:

```
OPENAI_BASE_URL=http://127.0.0.1:8080
OPENAI_API_KEY=<your-api-key>
GEMINI_API_KEY=
```

`GEMINI_API_KEY` is optional. Leave it blank to run on Groq only. Set it
to enable automatic failover: if Groq's request fails after retries, the
app calls Gemini directly instead (compressed via Paritok for summary
generation, same as the Groq path; raw for citation/relevance checks,
matching their existing uncompressed behavior). No restart of the Paritok
proxy is needed, just the backend.

Then start the API server:

```bash
backend/venv/Scripts/python -m uvicorn backend.api.main:app --reload --port 8000
```

On macOS or Linux, use `backend/venv/bin/python` instead.

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:3000`. The frontend expects the backend at `http://localhost:8000` by default; to point it elsewhere, set `NEXT_PUBLIC_API_BASE_URL` in a `.env.local` file inside `frontend/`.

### 3. Try it without setting anything up manually

To run the full pipeline once with a fixed query and see real output, run this from the repository root:

```bash
python -m backend.seed
```

This writes its result to `backend/data/seed_output.json`. Run it as a module (`python -m backend.seed`), not as a script directly (`python backend/seed.py`), since it uses absolute imports that need the repo root on `sys.path`.

### 4. Read the full documentation site locally

```bash
npm install
npm run docs:dev
```

Then open the local URL it prints (VitePress defaults to `http://localhost:5173`).

## Testing and measurement

The backend test suite covers retrieval, the search loop, summary generation, citation verification, the compression call, and the API routes end to end (23 test files under `backend/tests/`). Run it with:

```bash
backend/venv/Scripts/python -m pytest backend/tests
```

Token-savings numbers are produced by a dedicated measurement gate (`backend/measurement/run_gate.py`) that runs the real pipeline against a hand-written gold set. See [`docs/paritok-integration.md`](docs/paritok-integration.md) for the current numbers and what is still pending.

## Known limitations

- **Depth-first literature coverage.** The corpus currently spans 14 hand-selected conditions, a scope chosen to prove the verification pipeline holds up against the hardest case first, sparse and inconsistent rare-disease literature, before expanding breadth on top of a foundation that already works. Future work will scale ingestion to a live PubMed/Orphanet pipeline with automated quality filtering, so new conditions can be added without re-validating the whole system by hand.
- **Transparent citation flagging.** The citation checker labels unsupported claims and preserves them in the output, because a clinical-adjacent tool should let the user judge uncertainty rather than have the system hide it. Future work will let users filter or re-rank summaries by verification confidence directly in the interface, turning the flag from a passive label into an active control.
- **Request throttling under active development.** The API enforces per-endpoint rate limits, 10 requests per minute on query endpoints and 20 per minute on atlas lookups, a constraint set by the hackathon's Groq and Paritok quota ceilings during single-developer testing, and requests over the limit receive a proper 429 response with rate-limit headers rather than a silent drop. Future work will add usage-based tiers and a request queue, so demand beyond the free quota degrades gracefully instead of hitting a hard wall.

## Full documentation

This README covers the essentials. For the complete picture (diagrams, API reference, data model, every request-flow detail), start with [`docs/overview.md`](docs/overview.md) or run the VitePress site locally as shown above.

## License

Apache 2.0, see [LICENSE](LICENSE).
