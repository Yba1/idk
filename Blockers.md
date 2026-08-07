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
