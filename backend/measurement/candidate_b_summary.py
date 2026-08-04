"""Measurement gate, Candidate B (plan.md Step 2.1): the sourced-summary
call, which stuffs several retrieved abstracts into one prompt and compresses
the context block using compress_for_prompt, matching the actual Step 4.3
production summary flow.
"""
from __future__ import annotations

import json
from pathlib import Path

from backend.app.llm_client import compress_for_prompt

CORPUS_PATH = Path(__file__).resolve().parent.parent / "data" / "corpus.json"


def _build_stuffed_text(abstracts: list[dict]) -> str:
    """Format abstracts as a stuffed context block for compression."""
    return "\n\n".join(
        f"[{i+1}] PMID {p['pmid']} - {p['title']}\n{p['abstract']}"
        for i, p in enumerate(abstracts)
    )


def run_candidate_b() -> dict:
    """Measure compression across multiple sample prompts from different conditions.

    Samples 3-4 different conditions from the corpus with varying abstract counts
    (4-8 papers each) and measures compression via direct compress_for_prompt calls
    to match production's actual usage pattern in Step 4.3.
    """
    corpus = json.loads(CORPUS_PATH.read_text())

    # Sample diverse conditions with different sizes
    samples = [
        ("Scalp angiosarcoma", 6),
        ("Primary progressive aphasia semantic variant", 8),
        ("Primary angiitis of CNS", 5),
        ("Neurolymphomatosis CNS involvement", 4),
    ]

    total_original = 0
    total_compressed = 0

    for condition, n_abstracts in samples:
        # Sample abstracts for this condition
        condition_papers = [p for p in corpus if p.get("condition") == condition]
        abstracts = condition_papers[:n_abstracts]

        # If condition doesn't have enough papers, pad with other papers
        if len(abstracts) < n_abstracts:
            padding_needed = n_abstracts - len(abstracts)
            padding = [p for p in corpus if p.get("condition") != condition][:padding_needed]
            abstracts.extend(padding)

        if abstracts:
            stuffed = _build_stuffed_text(abstracts)
            # Use a generic query; the compression pipeline cares about the content size more
            _, original_tokens, compressed_tokens = compress_for_prompt(stuffed, "PET findings")
            total_original += original_tokens
            total_compressed += compressed_tokens

    reduction_pct = 0.0 if total_original == 0 else (total_original - total_compressed) / total_original * 100

    return {
        "proxied_prompt_tokens": total_compressed,
        "direct_prompt_tokens": total_original,
        "reduction_pct": round(reduction_pct, 2),
    }
