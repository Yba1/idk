"""FastAPI entrypoint. Run with:
    backend/venv/Scripts/python -m uvicorn backend.api.main:app --reload --port 8000
Loads .env before any route constructs a ParitokLLMClient, so the key never
passes through a Claude-visible tool call.
"""
from __future__ import annotations

import os
from pathlib import Path

root = Path(__file__).resolve().parent.parent.parent
env_path = root / ".env"
if env_path.exists():
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip())

from fastapi import FastAPI  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from slowapi import _rate_limit_exceeded_handler  # noqa: E402
from slowapi.errors import RateLimitExceeded  # noqa: E402

from backend.api.limiter import limiter  # noqa: E402
from backend.api.routes.atlas import router as atlas_router  # noqa: E402
from backend.api.routes.conditions import router as conditions_router  # noqa: E402
from backend.api.routes.demo import router as demo_router  # noqa: E402
from backend.api.routes.query import router as query_router  # noqa: E402

app = FastAPI(title="NeuLitTrace API")

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("FRONTEND_ORIGIN", "http://localhost:3000").split(","),
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

app.include_router(query_router)
app.include_router(demo_router)
app.include_router(conditions_router)
app.include_router(atlas_router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
