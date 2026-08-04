"""Reproducible demo run (plan.md Step 4.4): `git clone && run` should
produce the same demo state for a judge in under 5 minutes. Loads .env
internally so the key never passes through a Claude-visible tool call.
"""
from __future__ import annotations

import json
import os
from dataclasses import asdict
from pathlib import Path

root = Path(__file__).resolve().parent.parent
with open(root / ".env") as f:
    for line in f:
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ[key.strip()] = value.strip()

from backend.app.llm_client import ParitokLLMClient  # noqa: E402
from backend.app.loop.refine import run_search_loop  # noqa: E402
from backend.app.retrieval.demo_fixture import DEMO_QUERY, run_demo_contrast  # noqa: E402
from backend.app.retrieval.hybrid import HybridRetriever  # noqa: E402
from backend.app.summary.generate import generate_sourced_summary  # noqa: E402

CORPUS_PATH = Path(__file__).resolve().parent / "data" / "corpus.json"
OUT_PATH = Path(__file__).resolve().parent / "data" / "seed_output.json"


def run_seed_demo() -> dict:
    client = ParitokLLMClient()
    corpus = json.loads(CORPUS_PATH.read_text())
    retriever = HybridRetriever(corpus)

    demo_contrast = run_demo_contrast()
    papers, trace = run_search_loop(client, retriever, DEMO_QUERY)
    low_confidence = bool(trace) and not trace[-1].relevant
    summary = generate_sourced_summary(
        client, DEMO_QUERY, papers[:5] if papers else corpus[:5], low_confidence=low_confidence,
    )

    return {
        "demo_contrast": demo_contrast,
        "loop_trace": [asdict(t) for t in trace],
        "summary": asdict(summary),
    }


if __name__ == "__main__":
    output = run_seed_demo()
    OUT_PATH.write_text(json.dumps(output, indent=2))
    print(f"Seed demo run complete -> {OUT_PATH}")
