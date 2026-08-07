# Blockers

Append-only. "I need a change in a file I don't own." Names the file, the
change, and the owner. Owner makes the change, replies in-line, deletes the
entry.

## [c1] backend/api/dependencies.py still imports deleted v1 modules

**File:** `backend/api/dependencies.py` (Card 2A ownership)

**Problem:** `dependencies.py` still does, at module scope:

```python
from backend.app.llm_client import ParitokLLMClient
from backend.app.retrieval.hybrid import HybridRetriever
```

Both `backend/app/llm_client.py` and `backend/app/retrieval/hybrid.py` were
deleted at the freeze commit / by Card 1 respectively (freeze §2.1 deletes
`llm_client.py`; Card 1's phase card §3.4 deletes `hybrid.py`,
`bm25_index.py`, `vector_index.py`). Because `backend/api/routes/demo.py`
imports `get_demo_contrast` from `dependencies.py`, and `backend/api/main.py`
(FROZEN) includes the demo router, **the entire FastAPI app currently fails
to import** under `NEULIT_PROFILE=fake` with zero credentials — i.e. `from
backend.api.main import app` raises `ModuleNotFoundError` right now on
branch-1.

**Re-confirmed on branch-1 at commit `68a3ca2`** with a fresh run (no
credentials, `.venv-c1`):

```
NEULIT_PROFILE=fake .venv-c1/Scripts/python -c "from backend.api.main import app"
```

exact current traceback:

```
Traceback (most recent call last):
  File "<string>", line 1, in <module>
    from backend.api.main import app
  File "C:\Users\vivaa\idk-card1\backend\api\main.py", line 32, in <module>
    from backend.api.routes.demo import router as demo_router  # noqa: E402
    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\vivaa\idk-card1\backend\api\routes\demo.py", line 8, in <module>
    from backend.api.dependencies import get_demo_contrast
  File "C:\Users\vivaa\idk-card1\backend\api\dependencies.py", line 12, in <module>
    from backend.app.llm_client import ParitokLLMClient
ModuleNotFoundError: No module named 'backend.app.llm_client'
```

Still unresolved as of this re-check — no changes made to `dependencies.py`
(outside Card 1 ownership).

**Requested change:** `dependencies.py`'s `get_llm_client()` /
`get_retriever()` should resolve `LLMPort` / `RetrievalPort` implementations
via `backend.contracts.registry.get_services()` (as the ownership doc
intends — Card 1 builds the ports, Card 2A's app wires them through
`get_services()`), not import the deleted v1 classes directly.

**Workaround applied so Card 1's own test suite stays green in the
meantime:** `backend/tests/test_api_conditions.py` now mounts
`backend.api.routes.conditions.router` on a standalone `FastAPI()` instance
instead of importing `backend.api.main:app`. This is a workaround, not a
fix — the underlying app-level import failure is still present and will
affect any other lane's test that imports `backend.api.main`.

**Owner:** Card 2A. Not resolved by Card 1 because `backend/api/dependencies.py`
is outside Card 1's ownership bucket (plan-v2/00-SHARED-CONTRACTS.md §3).

**Copy-pasteable fix suggestion** (current `dependencies.py` lines 12-27,
verified against this branch-1 commit): replace the two stale imports and
the two functions that construct the deleted classes directly with calls
into `backend.contracts.registry.get_services()`, which already resolves
`RetrievalPort` / `LLMPort` implementations for the active `NEULIT_PROFILE`
(see `backend/contracts/registry.py`, FROZEN, and `config/services.yaml`
which maps `fake` -> Card 1's fake/stub implementations, `live_no_memory` /
`live` -> `CortexSearchRetriever` / `CortexLLMClient`):

```python
# remove:
# from backend.app.llm_client import ParitokLLMClient
# from backend.app.retrieval.hybrid import HybridRetriever

from backend.contracts.registry import get_services
from backend.contracts.ports import LLMPort, RetrievalPort

def get_llm_client() -> LLMPort:
    return get_services().llm

def get_retriever() -> RetrievalPort:
    return get_services().retrieval
```

`run_demo_contrast` (from `backend.app.retrieval.demo_fixture`, Card 1's
file, still present and unaffected) can keep calling whatever it currently
calls `get_retriever()` for — the return type is now the `RetrievalPort`
Protocol rather than the concrete deleted `HybridRetriever`, so any call
site that only uses `.search()` / `.closest_conditions()` / `.get_by_pmids()`
/ `.health()` (the Protocol's methods) needs no further change.

## [c1] Card 2A needs to wire backend/app/llm/compress.py into pipeline.py

**File:** `backend/app/pipeline.py` (Card 2A ownership)

**Not a bug/import failure like the entry above — a feature hand-off.**
`backend/app/llm/compress.py` (new, Card 1, this pass) exposes
`compress_papers_for_prompt(query, papers, top_n=4)` — extractive
sentence-level compression of retrieved paper abstracts, real measured
34.71% token reduction on the gold set (see
`backend/measurement/results/decision.md` section 4). It is fully
implemented and tested (`backend/tests/snowflake/test_compression.py`) but
**not called from anywhere in the live request path**, because prompt
assembly for the `summary` and `citation_check` call sites lives in
`backend/app/pipeline.py`, which is outside Card 1's ownership bucket.

**Requested change:** wherever `pipeline.py` builds the multi-paper
abstract text that goes into the `summary` and `citation_check` prompts,
call `compress_papers_for_prompt(query, [(p.pmid, p.abstract) for p in
papers], top_n=4)` and use each `PaperCompression.result.text` in place of
the raw abstract, keyed by `pmid` so citation markers stay aligned to the
right paper. `hyde`, `relevance_check`, `refine`, and `memory_distill`
should NOT be touched — they don't build multi-paper abstract prompts.

**Owner:** Card 2A. Not resolved by Card 1 because `backend/app/pipeline.py`
is outside Card 1's ownership bucket (`scripts/ownership.txt`).

## [c1] .env.example needs two new optional env vars documented (Phase E routing)

**File:** `.env.example` (repo root, not in Card 1's ownership bucket per
`scripts/ownership.txt` -- not listed there at all, so not touched
unilaterally).

**Context:** Phase E (`backend/app/llm/routing.py`, wired into
`CortexLLMClient.chat()` in `backend/snowflake/llm.py`) adds two new
optional env vars: `SNOWFLAKE_CORTEX_MODEL_CHEAP` and
`SNOWFLAKE_CORTEX_MODEL_STRONG`. Both are optional -- if unset, the
existing `SNOWFLAKE_CORTEX_MODEL` is used for every call site exactly as
before (backward compatible, no behavior change for anyone not opting in).

**Requested change:** add, near the existing `SNOWFLAKE_CORTEX_MODEL=
claude-3-5-sonnet` line:

```
SNOWFLAKE_CORTEX_MODEL_CHEAP=
SNOWFLAKE_CORTEX_MODEL_STRONG=
```

with a short comment noting they're optional per-call-site-tier overrides
(see `backend/app/llm/routing.py`'s module docstring for the full
priority order and default model choices).

**Owner:** whoever owns `.env.example` (unclear from `scripts/ownership.txt`
which doesn't mention this file at all -- flagged here rather than edited
unilaterally, per the same out-of-bucket rule as the other entries above).
