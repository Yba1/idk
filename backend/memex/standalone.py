"""Zero-touch fallback: MemEx as its own FastAPI app, on its own port.

Route A (preferred) is two lines in backend/api/main.py via wire.attach().
Route B is this file: if there is any resistance to editing a FROZEN file, or
if their app is red for an unrelated reason at 14:30, MemEx still demos.

    uvicorn backend.memex.standalone:app --port 8001

Then point the frontend (or the demo script) at http://localhost:8001. CORS is
open to the same origin their main app uses.
"""
from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.routes.memex import router as memex_router

app = FastAPI(title="MemEx API (standalone)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("FRONTEND_ORIGIN", "http://localhost:3000").split(","),
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

app.include_router(memex_router)


@app.get("/health")
def health() -> dict:
    from backend.contracts.registry import get_services

    services = get_services()
    ports = {
        "retrieval": services.retrieval.health(),
        "llm": services.llm.health(),
        "memory": services.memory.health(),
        "ledger": services.ledger.health(),
    }
    status = "ok" if all(p.get("ok") for p in ports.values()) else "degraded"
    return {"status": status, "ports": ports, "mode": "memex-standalone"}
