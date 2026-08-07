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


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    if _live_credentials_present():
        return
    skip_live = pytest.mark.skip(
        reason=(
            "live Snowflake credentials not set "
            f"({', '.join(_REQUIRED_LIVE_ENV_VARS)}); run by hand with "
            "`pytest -m live backend/tests/snowflake` once you have a real account."
        )
    )
    for item in items:
        if "live" in item.keywords:
            item.add_marker(skip_live)
