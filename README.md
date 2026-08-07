# NeuLitTrace

**A memory-aware, cost-transparent literature research assistant for rare and uncommon neurological findings.**

NeuLitTrace searches a focused corpus of neuroimaging case reports and papers, checks relevance before answering, writes a cited summary, remembers what a researcher has already explored, and attaches a real dollar cost to every answer it gives.

<img src="docs/public/screenshots/04-results-full.png" alt="NeuLitTrace sourced summary with brain region highlight and numbered citations" width="900" />

---

## Table of contents

- [The problem](#the-problem)
- [Who this is for](#who-this-is-for)
- [What it is not](#what-it-is-not)
- [How it works](#how-it-works)
- [Snowflake integration](#snowflake-integration)
- [EverMind memory](#evermind-memory)
- [Cost of Intelligence: compression, caching, and model routing](#cost-of-intelligence-compression-caching-and-model-routing)
- [Retrieval policy: the breadth-vs-depth dial](#retrieval-policy-the-breadth-vs-depth-dial)
- [MemEx: pricing memory as an asset](#memex-pricing-memory-as-an-asset)
- [Stack](#stack)
- [Repository structure](#repository-structure)
- [Quickstart](#quickstart)
- [Testing](#testing)
- [Known limitations](#known-limitations)
- [Documentation](#documentation)
- [License](#license)

---

## The problem

A published pilot study at Seoul National University Hospital tested nearly this exact approach — retrieval-augmented generation over PET case reports. On common cases it worked well: 84.2% of routine cases retrieved relevant matches, agreed upon by three physician readers. On rare cases it broke down. It failed to retrieve a documented case of scalp angiosarcoma *specifically because the condition was rare*. The authors named better rare-case retrieval as necessary future work.

That is the exact gap this project targets: retrieval built to favor rare and underexplored conditions instead of penalizing them — plus the two things most RAG demos skip: personalization that doesn't quietly bury the signal that matters, and cost that isn't a black box.

## Who this is for

- Clinicians investigating uncommon neurological presentations
- Researchers building a trail across related conditions over multiple sessions
- Teams evaluating the cost and reliability of multi-step LLM agent pipelines

## What it is not

NeuLitTrace is **not** a diagnostic device, a substitute for clinical judgment, or a comprehensive medical index. It is a focused research demo whose every claim stays linked to a source paper — a clinician must still review every citation.

## How it works

1. A query loads the researcher's EverMind profile when personalization is enabled.
2. Snowflake Cortex Search retrieves papers from the corpus (hybrid lexical + vector, natively).
3. A rarity boost re-ranks results so uncommon conditions surface instead of being buried under common ones; memory applies a second, *bounded* re-rank on top so prior work can help without overpowering that rarity signal.
4. Cortex `COMPLETE` runs the applicable calls across six named inference call sites (`hyde`, `relevance_check`, `refine`, `summary`, `citation_check`, `memory_distill`) and produces a sourced summary.
5. Every inference call writes a priced row to `TOKEN_LEDGER` — prompt tokens, completion tokens, and USD cost, per call site.
6. The economics view aggregates spend by step and hour; Cortex Analyst answers natural-language questions about those records ("which pipeline step is most expensive?").
7. The thread and distilled researcher profile are updated for the next query.

The backend exposes retrieval, inference, memory, and the ledger through separate ports (`backend/contracts/ports.py`). A memory or ledger outage degrades one capability instead of collapsing the whole request.

## Snowflake integration

Snowflake provides corpus retrieval through Cortex Search, inference through Cortex `COMPLETE`, per-call economics in `TOKEN_LEDGER`, aggregate economics views, and a Cortex Analyst natural-language surface. The UI shows values returned by the ledger, never a substituted benchmark claim.

**Live account verification** confirmed: 329 papers, 14 conditions, 10 rare conditions loaded; an active Cortex Search service over all 329 rows; a successful `claude-sonnet-4-5` `COMPLETE` call; and ledger read-back for both successful and degraded calls. 3 of 4 Tier-2 live tests passed — the failing test confirmed the Analyst call shape needs to move to the dedicated Cortex Analyst REST API, tracked as follow-up work.

## EverMind memory

EverMind stores a researcher profile and query thread — specialty, explored conditions, distilled context, and seen papers. Its re-rank multiplier is deliberately capped to `[0.6, 1.2]`: personalization can reduce repetition and gently reinforce relevant prior work, but it cannot overpower the retrieval rarity signal that makes rare-condition recall the whole point. A 300ms budget keeps memory optional — timeout or failure returns an explicitly unpersonalized answer rather than blocking the response.

## Cost of Intelligence: compression, caching, and model routing

Three independent, stackable cost-reduction mechanisms, each with a real, reproducible measurement — no invented numbers.

| Mechanism | What it does | Measured result |
|---|---|---|
| **Extractive compression** (`backend/app/llm/compress.py`) | Scores each retrieved abstract's sentences by query-term overlap, keeps only the top-N most relevant per paper before it reaches the `summary`/`citation_check` prompt | **34.71% token reduction** (64,947 → 42,401 tokens across 280 compressed abstracts, 28-query gold set); ~13.88% cost reduction on a representative summary-shaped call |
| **In-process TTL prompt cache** (`backend/app/llm/cache.py`) | Caches `hyde`/`relevance_check` responses by a hash of the normalized prompt; a cache hit skips the Cortex `COMPLETE` call entirely | Exercises the real cache mechanics end-to-end (hand-rolled TTL dict, no new dependency); hit-rate numbers are reported honestly as a synthetic repeat-query exercise, not an organic-traffic claim — see `backend/measurement/results/cost_of_intelligence.json` |
| **Call-site model routing** (`backend/app/llm/routing.py`) | Routes quality-tolerant, binary-gate calls (`hyde`, `relevance_check`) to a cheaper model tier; reserves the strongest model for calls where output quality matters most (`summary`, `citation_check`) | **98.33% cost reduction** on the `hyde` call-site (real published Snowflake AI Credit rate, $0.30/Mtok-out for the cheap tier vs. the default model) |

All three run credential-free against `FakeRetrieval`/mocked Snowpark sessions in CI, and are additive — a live re-run against real Snowflake traffic is the next step to convert these into organic, account-billed figures. Full methodology, caveats, and exact commands to reproduce every number: `backend/measurement/results/decision.md` and `backend/measurement/results/cost_of_intelligence.json`.

## Retrieval policy: the breadth-vs-depth dial

Over-retrieval has a specific clinical justification here: rare conditions are exactly the ones a top-10 cutoff buries. Neurolymphomatosis has 4 papers and Primary angiitis of CNS has 5, against 40 each for the most common conditions, in a 329-paper corpus.

`backend/app/retrieval/policy.py` exposes two named policies:

| Policy | `top_k` | `compress_top_n` | Behavior |
|---|---|---|---|
| **TIGHT** | 10 | 4 | Today's default retrieval breadth |
| **GENEROUS** | 30 | 1 | 3x the papers, 1 sentence each |

Measured over the same 28-query gold set:

| Metric | TIGHT | GENEROUS | Δ |
|---|---|---|---|
| Prompt tokens | 42,401 | 42,110 | **−0.69%** |
| Summary cost | $0.3038 | $0.3028 | **−0.34%** |
| Rare-condition recall | 0.4118 | 0.7475 | **+81.52%** |
| Zero-hit queries | 3 | 1 | −2 |

GENEROUS improved 17 of 20 rare queries and regressed on none — and costs *less*, not more, because `backend/snowflake/retrieval.py` already over-fetches `max(top_k*4, 40)` candidates from Cortex Search and discards past `top_k`, so widening to `k=30` is the same underlying search call. `GENEROUS` is a measured setting, not a guess: `run_policy_bench.py` sweeps the full grid, and `k=30/n=1` is the widest configuration that still stays inside `TIGHT`'s token budget — `k=40/n=1` buys another +0.06 rare recall for +31% tokens, i.e. breadth keeps paying off, it just stops being free past that point. Full numbers and caveats: `backend/measurement/results/policy_bench.md`.

## MemEx: pricing memory as an asset

A memory-cost marketplace layered on top of everything above, aimed at making "memory saves money" into an actual, tradeable number instead of an adjective.

- **Cold vs. warm comparison** (`backend/memex/engine.py`): answers the identical question two ways — COLD (no memory, full abstracts, premium model, re-billed every turn) vs. WARM (a compact digest of what the researcher's profile already knows). Both paths get the exact same prompt and question, so the comparison measures memory's value, not prompt engineering.
- **Scarcity-weighted pricing** (`backend/memex/scarcity.py`): a real inverse-document-frequency formula over the corpus — `multiplier(c) = ln(N / n_c) / ln(N / n_max)` — so a fact about a 4-paper condition prices meaningfully higher than a fact about a 40-paper one, computed from data, not a hand-picked constant.
- **Published, cited rates** (`backend/memex/pricing.py`): every dollar figure is a measured token count multiplied by a rate transcribed directly from Snowflake's Service Consumption Table PDF (effective 2026-07-31), not estimated or recalled from memory.
- **A marketplace, honestly scoped** (`backend/memex/market.py`): the peer "agents" (`attending`, `sage`) are scripted ledger rows with names, not autonomous agents — there is no agent-to-agent negotiation protocol. What's real is the price math itself.

Endpoints: `GET /memex/health`, `POST /memex/query` (the cold/warm comparison, optionally settling a trade), `GET /memex/market` (wallets and trade history), `POST /memex/shock` (destroy a memory, re-price the same question live, show the resulting price spike — verified against the corpus's scarcest condition, Neurolymphomatosis, scarcity multiplier 2.093).

## Stack

- **Frontend:** Next.js 16, React 19, TypeScript, Tailwind CSS
- **Backend:** FastAPI, with an OpenAPI-generated frontend client contract
- **Data platform:** Snowflake — Cortex Search, Cortex `COMPLETE`, Cortex Analyst, and token-ledger views
- **Memory:** EverMind / EverOS
- **Docs:** VitePress, D2 diagram sources

## Repository structure

```text
frontend/   Next.js product UI and Playwright tests
backend/    API routes, orchestration pipeline, ports, and Snowflake/memory/memex adapters
snowflake/  DDL, Cortex Search service definition, semantic model, setup docs
docs/       VitePress documentation and architecture diagrams
plan-v2/    The three-lane build plan and shared contracts this project was built against
```

## Quickstart

Start the credential-free backend profile (no Snowflake account needed):

```bash
NEULIT_PROFILE=fake python -m uvicorn backend.api.main:app --reload --port 8000
```

Then run the frontend:

```bash
cd frontend
npm ci
npm run types:gen
npm run dev
```

Open `http://localhost:3000`. The full API contract is available at `http://localhost:8000/openapi.json`.

Build the documentation from the repository root:

```bash
npm ci
npm run docs:dev
```

To run against a real Snowflake account, see `snowflake/sql/README.md` for the DDL run order, then set `NEULIT_PROFILE=live` (or `live_no_memory` to skip EverOS credentials) and the `SNOWFLAKE_*` env vars documented in `.env.example`.

## Testing

```bash
python -m pytest backend/tests -q
```

Tier 1 tests are fully credential-free (`NEULIT_PROFILE=fake`, zero `SNOWFLAKE_*`/`EVEROS_*` env vars) and run in CI. Tier 2 tests (`@pytest.mark.live`) exercise real Snowflake/Cortex and are auto-skipped unless real credentials are present — run them explicitly with `pytest -m live` once you have an account configured.

## Known limitations

- **Focused corpus:** coverage is limited to 329 papers across 14 conditions. Future work should add governed ingestion and wider neurological coverage.
- **Not real-time:** Cortex Search's `TARGET_LAG` means newly loaded records aren't immediately searchable. Future work should expose index freshness in health metadata.
- **Demo identity model:** memory uses a single namespace and trusts `user_id`; there is no authentication boundary. Production use requires authenticated tenancy and namespace isolation.
- **Memory is bounded and optional by design:** the `[0.6, 1.2]` re-rank cap deliberately limits personalization so it can't create a filter bubble that outranks rarity.
- **Economics depend on the ledger:** when the ledger is unavailable, answers still render but cost is marked unavailable rather than guessed.
- **Live economics validation is partial:** row counts, Search, `COMPLETE`, ledger insert/read-back, and one full live query were exercised. Account billing rates for cheaper-tier models are still list-price research, not account-reconciled, and the Cortex Analyst REST integration is the one Tier-2 test still failing.
- **Least privilege is not finished:** live setup used an `ACCOUNTADMIN`-scoped token for hackathon validation. Deployment must rotate it and run the application under the scoped `NEULIT_APP` role.
- **MemEx's peer agents are scripted, not autonomous:** stated plainly in the module itself — there is no agent-to-agent negotiation protocol underneath the pricing.
- **Not clinical advice:** summaries can be incomplete or wrong despite citation checks. A clinician must review every source.

## Documentation

Start with the [overview](docs/overview.md), then see [architecture](docs/architecture.md), [token economy](docs/token-economy.md), [memory](docs/memory.md), and the [API reference](docs/api-reference.md).

## License

See [LICENSE](LICENSE).
