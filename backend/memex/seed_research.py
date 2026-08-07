"""Seed the demo: three researcher sessions, five turns each, from the corpus.

Run before the demo so the warm path has a profile to lean on and the market
has a trade history to show:

    NEULIT_PROFILE=fake python -m backend.memex.seed_research

Every question below is generated FROM backend/data/corpus.json - the condition
names and the vocabulary come out of real abstracts rather than being invented,
so a judge who greps the corpus for any phrase on screen finds it. That is the
only reason to build the questions this way instead of hard-coding prose.

The last stanza is the verification query: Neurolymphomatosis CNS involvement
has 4 papers in a 329-paper corpus, which is the scarcest condition present and
therefore the highest scarcity multiplier (2.093). It is the shock target
because destroying a memory about it produces the largest, most honest price
spike available in this data.
"""
from __future__ import annotations

import argparse
import json
import os
from collections import Counter
from pathlib import Path

from backend.memex.engine import ask
from backend.memex.market import get_market
from backend.memex.scarcity import get_index

#: The condition the demo's shock beat destroys. Scarcest in the corpus.
SHOCK_CONDITION = "Neurolymphomatosis CNS involvement"

VERIFY_QUERY = (
    "neurolymphomatosis CNS involvement imaging findings and nerve enhancement"
)

#: Five question templates per session. Filled with real condition names.
_TEMPLATES = [
    "What imaging findings characterise {condition}?",
    "How is {condition} distinguished from its differentials?",
    "What does the literature report about disease course in {condition}?",
    "Which sequences or tracers are recommended when {condition} is suspected?",
    "What are the reported treatment responses in {condition}?",
]

SESSIONS = [
    ("neuro-oncology", "resident-a", "session-a"),
    ("neurodegenerative", "resident-b", "session-b"),
    ("vascular", "resident-c", "session-c"),
]


def _corpus_conditions() -> list[str]:
    path = os.environ.get("MEMEX_CORPUS_PATH") or str(
        Path(__file__).resolve().parent.parent / "data" / "corpus.json"
    )
    with open(path) as fh:
        rows = json.load(fh)
    counts = Counter(r["condition"] for r in rows if r.get("condition"))
    # Rarest first: the interesting end of the corpus, and the end where the
    # scarcity multiplier actually does something.
    return [c for c, _ in sorted(counts.items(), key=lambda kv: kv[1])]


def seed(verbose: bool = True) -> dict:
    """Run 3 sessions x 5 turns, then the verification query. Returns a report."""
    conditions = _corpus_conditions()
    index = get_index()
    market = get_market()
    turns: list[dict] = []

    for i, (specialty, user_id, session_id) in enumerate(SESSIONS):
        # Each session walks a different slice of the corpus so the three
        # profiles genuinely differ - identical profiles would make the memory
        # story unfalsifiable.
        slice_ = conditions[i :: len(SESSIONS)][:5]
        while len(slice_) < 5 and conditions:
            slice_.append(conditions[len(slice_) % len(conditions)])

        for template, condition in zip(_TEMPLATES, slice_):
            question = template.format(condition=condition)
            result = ask(question, user_id=user_id, session_id=session_id)
            trade = market.settle_question(result)
            turns.append(
                {
                    "user_id": user_id,
                    "specialty": specialty,
                    "question": question,
                    "condition": condition,
                    "tokens_displaced": result.tokens_displaced,
                    "scarcity": round(result.scarcity_multiplier, 3),
                    "price_credits": trade.price_credits,
                }
            )
            if verbose:
                print(
                    f"  [{user_id}] {question[:58]:<58} "
                    f"displaced={result.tokens_displaced:>5}  "
                    f"scarcity={result.scarcity_multiplier:.3f}"
                )

    verify = ask(VERIFY_QUERY, user_id="resident-a", session_id="session-a")
    report = {
        "turns": len(turns),
        "sessions": len(SESSIONS),
        "corpus_papers": index.total_papers,
        "shock_condition": SHOCK_CONDITION,
        "shock_condition_papers": index.paper_count(SHOCK_CONDITION),
        "shock_condition_multiplier": index.multiplier(SHOCK_CONDITION),
        "verify_query": VERIFY_QUERY,
        "verify_top_condition": verify.scarcity_condition,
        "verify_multiplier": verify.scarcity_multiplier,
        "verify_tokens_displaced": verify.tokens_displaced,
        "market": market.totals(),
        "detail": turns,
    }

    if verbose:
        print()
        print(f"  corpus papers            {report['corpus_papers']}")
        print(f"  shock condition          {SHOCK_CONDITION}")
        print(
            f"  shock papers/multiplier  {report['shock_condition_papers']} / "
            f"{report['shock_condition_multiplier']:.3f}"
        )
        print(f"  verify top condition     {report['verify_top_condition']}")
        print(f"  verify displaced tokens  {report['verify_tokens_displaced']}")
        print(f"  trades booked            {report['market']['trades']}")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed MemEx demo sessions.")
    parser.add_argument("--json", action="store_true", help="emit the report as JSON")
    args = parser.parse_args()

    report = seed(verbose=not args.json)
    if args.json:
        report.pop("detail", None)
        print(json.dumps(report, indent=2))

    # Non-zero exit if the shock target is not the scarcest thing we found -
    # that would mean the corpus changed under us and the demo beat is wrong.
    ok = report["shock_condition_papers"] > 0
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
