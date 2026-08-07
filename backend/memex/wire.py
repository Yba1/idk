"""The hook into their FastAPI app.

backend/api/main.py is FROZEN and does not include a memex router. Adding one
costs exactly two lines there, and this module exists so it is only ever two
lines - every future MemEx route is added inside our own package and main.py
never has to be touched again.

At merge time, in backend/api/main.py:

    from backend.memex.wire import attach          # noqa: E402
    attach(app)                                    # after the include_router block

If Bryan would rather not touch a FROZEN file at all, use
backend/memex/standalone.py instead and run MemEx on its own port - zero edits
to any existing file. See MERGE_PLAYBOOK.md, "Route B".
"""
from __future__ import annotations

from typing import Any


def attach(app: Any) -> Any:
    """Mount the MemEx router onto an existing FastAPI app. Idempotent."""
    from backend.api.routes.memex import router as memex_router

    if getattr(app.state, "memex_attached", False):
        return app
    app.include_router(memex_router)
    app.state.memex_attached = True
    return app
