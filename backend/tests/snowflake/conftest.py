"""Owned by Card 1 (backend/tests/snowflake/* is in the c1 ownership bucket).

Registers the `live` marker so pytest doesn't warn (PytestUnknownMarkWarning)
when it sees `@pytest.mark.live` in test_live_snowflake.py, and auto-skips
any test marked `live` unless real SNOWFLAKE_* credentials are present in the
environment. This keeps Tier 1 (`pytest` with no args) green with zero
Snowflake credentials, while still letting a human with real credentials run
`pytest -m live backend/tests/snowflake` by hand.

No repo-root pytest.ini exists and adding one is outside Card 1's ownership
bucket (scripts/ownership.txt has no root-level config entry for any lane),
so marker registration + skip logic lives here instead. See Blockers.md /
Handoff-Log.md for the reasoning.
"""
from __future__ import annotations

import os

import pytest

_REQUIRED_LIVE_ENV_VARS = (
    "SNOWFLAKE_ACCOUNT",
    "SNOWFLAKE_USER",
    "SNOWFLAKE_PASSWORD",
)


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "live: requires a real Snowflake connection (SNOWFLAKE_* env vars); "
        "skipped by default, run by hand with `pytest -m live`.",
    )


def _live_credentials_present() -> bool:
    return all(os.environ.get(var) for var in _REQUIRED_LIVE_ENV_VARS)


def _live_explicitly_requested(config: pytest.Config) -> bool:
    """True only when the run asked for the `live` marker by name.

    Credential *presence* is not a safe trigger. `backend/api/main.py` loads
    `.env` into os.environ at import time (by design, so a key never passes
    through a tool call), so the moment any test in the suite imports the app,
    every SNOWFLAKE_* var appears in the environment -- and a bare `pytest`
    would start firing real network calls at whatever account happens to be
    configured. Worse, presence never implied *working*: an account with MFA
    enrolled rejects password auth for programmatic access entirely, so the
    vars can be perfectly well-formed and still fail to connect.

    Opt-in by marker is what the module docstring always promised, and it is
    the only gate that survives `.env` existing.
    """
    return "live" in (config.option.markexpr or "")


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    if _live_explicitly_requested(config) and _live_credentials_present():
        return

    if not _live_explicitly_requested(config):
        reason = (
            "live Snowflake tests are opt-in; run them with "
            "`pytest -m live backend/tests/snowflake`."
        )
    else:
        reason = (
            "live Snowflake credentials not set "
            f"({', '.join(_REQUIRED_LIVE_ENV_VARS)}); set them in .env or the "
            "environment, then re-run `pytest -m live backend/tests/snowflake`."
        )

    skip_live = pytest.mark.skip(reason=reason)
    for item in items:
        if "live" in item.keywords:
            item.add_marker(skip_live)
