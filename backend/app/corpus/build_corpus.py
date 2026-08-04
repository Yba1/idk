"""One-time corpus fetch (plan.md Step 2.5). Run manually via
`python -m backend.app.corpus.build_corpus`, not on every app start -
the corpus is a fixed, cached local dataset, not a live per-query fetch.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

from backend.app.corpus.conditions import CONDITIONS, Condition
from backend.app.corpus.fetch_pubmed import fetch_abstracts, search_pmids

DEFAULT_OUT_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "corpus.json"


def build_corpus(conditions: list[Condition], out_path: Path) -> list[dict]:
    papers: list[dict] = []
    for condition in conditions:
        pmids = search_pmids(condition.pubmed_query, retmax=condition.target_count)
        time.sleep(0.4)  # stay under the ~3 req/sec unauthenticated E-utils limit
        fetched = fetch_abstracts(pmids)
        time.sleep(0.4)
        for paper in fetched:
            papers.append({
                **paper,
                "condition": condition.name,
                "rarity": condition.rarity,
                "region_literature": condition.region_literature,
                "atlas_label": condition.atlas_label,
                "overlaps_with": condition.overlaps_with,
            })

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(papers, indent=2))
    return papers


if __name__ == "__main__":
    result = build_corpus(CONDITIONS, DEFAULT_OUT_PATH)
    print(f"Fetched {len(result)} papers across {len(CONDITIONS)} conditions -> {DEFAULT_OUT_PATH}")
