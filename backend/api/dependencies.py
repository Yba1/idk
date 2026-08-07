"""FastAPI dependency accessors. get_services() itself is already a cached
singleton (backend.contracts.registry, FROZEN); this only exposes it via
Depends() so routes that touch ports directly (not through pipeline.run_query,
which resolves services on its own) can be swapped in tests via
app.dependency_overrides.
"""
from __future__ import annotations

from backend.contracts.registry import Services, get_services


def get_services_dep() -> Services:
    return get_services()
