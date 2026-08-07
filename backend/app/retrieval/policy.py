"""Retrieval policy -- the breadth/depth dial behind the cost story.

A policy is two integers and a label. It says how many papers to put in front
of the model (`top_k`) and how much of each paper survives extractive
compression (`compress_top_n`, passed straight to
`backend/app/llm/compress.py`). Nothing else. The retrieval algorithm, the
rarity boost, and the compression scorer are all unchanged -- this module only
decides where their dials are set.

--- WHY THIS EXISTS --------------------------------------------------------

The founding citation in README.md is a published pilot that retrieved well on
common cases and failed on a rare one (scalp angiosarcoma) *because it was
rare*. Our own gold set reproduces that failure: with `TIGHT`, some rare
conditions surface zero relevant papers -- not "ranked low", zero. The corpus
makes the reason obvious: Neurolymphomatosis has 4 papers and Primary angiitis
of CNS has 5, against 40 each for the four common conditions. A top-10 cut over
329 papers is structurally hostile to a 4-paper condition.

The fix is to look at more papers. The reason nobody does is that more papers
means a bigger prompt means a bigger bill. So the two dials move together:

    TIGHT      top_k=10, compress_top_n=4   -- depth. 10 papers, 4 sentences each.
    GENEROUS   top_k=30, compress_top_n=1   -- breadth. 30 papers, 1 sentence each.

Three times the papers, a quarter of the text per paper, for the same money.
`GENEROUS`'s exact shape is not a guess -- `run_policy_bench.py` sweeps the
(top_k, compress_top_n) grid and k=30/n=1 is the measured iso-cost point:
42,110 prompt tokens against TIGHT's 42,401 over the 28-query gold set, i.e.
0.7% *under* budget, while mean rare-condition recall goes 0.4118 -> 0.7475 and
the count of queries that surface zero relevant papers goes 3 -> 1. Wider
settings do keep buying recall, but they stop being free: k=40/n=1 costs +31%
tokens for a further +0.06 rare recall.

--- THE PART THAT MAKES IT NEARLY FREE -------------------------------------

`backend/snowflake/retrieval.py`'s `search()` already does:

    over_fetch = max(top_k * 4, 40)

It fetches 40 candidates, applies the rarity re-rank, and discards everything
past `top_k`. So at `top_k=40` the Cortex Search call is the *same call* --
same row scan, same service, same latency budget. Going generous does not buy
extra retrieval; it stops throwing away retrieval already paid for.

--- WHAT THIS IS NOT -------------------------------------------------------

Not adaptive. A policy is chosen per request by the caller, not inferred from
the query. Query-adaptive policy (cheap for common conditions, generous for
suspected-rare ones) is the obvious next step and is deliberately not here --
it would make the A/B two variables instead of one.
"""
from __future__ import annotations

from dataclasses import dataclass

from backend.app.llm.compress import DEFAULT_TOP_N


@dataclass(frozen=True)
class RetrievalPolicy:
    """How many papers to retrieve, and how hard to compress each one.

    `top_k` goes to `RetrievalPort.search(top_k=...)`; `compress_top_n` goes
    to `compress_papers_for_prompt(top_n=...)`. Frozen so a policy can be a
    module-level constant without any caller being able to mutate the shared
    instance.
    """

    top_k: int
    compress_top_n: int
    label: str

    def __post_init__(self) -> None:
        if self.top_k < 1:
            raise ValueError(f"top_k must be >= 1, got {self.top_k}")
        if self.compress_top_n < 1:
            raise ValueError(f"compress_top_n must be >= 1, got {self.compress_top_n}")

    @property
    def sentence_budget(self) -> int:
        """Upper bound on sentences reaching the prompt: `top_k * compress_top_n`.

        An upper bound, not a measurement -- `compress_abstract` skips
        compression for abstracts with fewer than 3 sentences and returns them
        whole, so a real prompt can exceed this. Useful for reasoning about two
        policies *before* running them; use the measured `tokens_after` totals
        from the bench for any number that gets quoted.
        """
        return self.top_k * self.compress_top_n


# Today's retrieval breadth (`pipeline.RETRIEVAL_TOP_K` and
# `RetrievalPort.search`'s default `top_k` are both 10) at the compressor's own
# default depth. `compress_top_n` is defined in terms of `DEFAULT_TOP_N` rather
# than a literal 4 so it cannot silently drift from the compressor's default.
#
# Caveat worth keeping honest: `pipeline.run_query` does not currently apply
# compression at all (it cuts to SUMMARY_TOP_N=5 full abstracts), so TIGHT is
# the policy-space representation of today's retrieval, not a byte-for-byte
# replay of today's summary prompt.
TIGHT = RetrievalPolicy(top_k=10, compress_top_n=DEFAULT_TOP_N, label="tight")

# The measured iso-cost point (see the module docstring): the widest setting
# that still lands at or under TIGHT's prompt-token budget on the gold set.
GENEROUS = RetrievalPolicy(top_k=30, compress_top_n=1, label="generous")

DEFAULT_POLICY = TIGHT

_BY_LABEL = {p.label: p for p in (TIGHT, GENEROUS)}


def policy_for_label(label: str) -> RetrievalPolicy:
    """Resolve a named policy. Raises on an unknown label rather than falling
    back to a default -- a typo'd policy name in a bench config or an API
    payload should fail loudly, not silently measure the wrong arm.
    """
    try:
        return _BY_LABEL[label]
    except KeyError:
        known = ", ".join(sorted(_BY_LABEL))
        raise ValueError(f"unknown retrieval policy {label!r} (known: {known})") from None
