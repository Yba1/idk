"""Reproducible demo run: `python -m backend.seed [--profile PROFILE]` runs
run_query once against a fixed query and writes backend/data/seed_output.json.
Loads .env internally so the key never passes through a Claude-visible tool call.
"""
from __future__ import annotations

import argparse
import json
import os
from dataclasses import asdict
from pathlib import Path

root = Path(__file__).resolve().parent.parent
env_path = root / ".env"
if env_path.exists():
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip())

from backend.app.pipeline import run_query  # noqa: E402
from backend.contracts.registry import get_services  # noqa: E402

DEMO_QUERY = "localized hypermetabolic uptake pattern on brain imaging"
OUT_PATH = Path(__file__).resolve().parent / "data" / "seed_output.json"


def run_seed_demo(*, profile: str | None = None) -> dict:
    if profile:
        os.environ["NEULIT_PROFILE"] = profile
        get_services.cache_clear()

    result = run_query(DEMO_QUERY, user_id="seed-user", session_id="seed-session", personalize=True)
    return asdict(result)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", default=None, help="Override NEULIT_PROFILE for this run")
    args = parser.parse_args()

    output = run_seed_demo(profile=args.profile)
    OUT_PATH.write_text(json.dumps(output, indent=2))
    print(f"Seed run complete -> {OUT_PATH}")
