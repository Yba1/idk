"""Extractive context compression for retrieved-paper abstracts.

Hackathon "Cost of Intelligence" feature, added on top of the original phase
card scope. Scores each sentence of a paper's abstract by query-term overlap
(same tokenizer/overlap idea as backend/contracts/fakes.py's `_tokenize` and
backend/app/retrieval/rarity.py's boost multiplier -- reused here rather than
reinvented) and keeps only the top-N highest scoring sentences per paper
before that abstract goes into an LLM prompt.

This module does NOT wire itself into prompt assembly for `summary` /
`citation_check` -- that code lives in backend/app/pipeline.py, which is
Card 2A's ownership (see scripts/ownership.txt), not Card 1's. It exposes a
clean, independently-testable function; see Handoff-Log.md and Blockers.md
for the hand-off note asking Card 2A to call `compress_paper_abstract` /
`compress_papers_for_prompt` at the `summary` and `citation_check` call
sites.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from backend.app.llm.tokenizer import estimate_tokens

# Same tokenizer pattern as backend/contracts/fakes.py's _tokenize / the
# overlap logic backend/app/retrieval/rarity.py's boost is layered on top
# of -- word == run of alnum chars, lowercased, deduped into a set.
_WORD_RE = re.compile(r"[a-z0-9]+")

# Crude but adequate sentence splitter for PubMed-style abstracts: split on
# '.', '!', '?' followed by whitespace + a capital letter or end of string.
# Abstracts in this corpus are single-paragraph prose, not code or lists.
_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9])")

DEFAULT_TOP_N = 4
_MIN_SENTENCES_TO_COMPRESS = 3  # below this, compression is skipped (Phase A.4)


def _tokenize(text: str) -> set[str]:
    return set(_WORD_RE.findall(text.lower()))


def split_sentences(text: str) -> list[str]:
    text = text.strip()
    if not text:
        return []
    parts = [s.strip() for s in _SENTENCE_RE.split(text) if s.strip()]
    return parts


def _overlap_score(query_tokens: set[str], sentence: str) -> float:
    sentence_tokens = _tokenize(sentence)
    if not sentence_tokens:
        return 0.0
    return float(len(query_tokens & sentence_tokens))


@dataclass(frozen=True)
class CompressionResult:
    """Per-paper compression outcome, with before/after token counts so the
    % reduction is measured (via backend/app/llm/tokenizer.py's existing
    estimator) rather than guessed.
    """

    text: str
    sentences_kept: int
    sentences_total: int
    tokens_before: int
    tokens_after: int
    skipped: bool  # True when too few sentences to safely trim (falls back to full text)

    @property
    def tokens_saved(self) -> int:
        return max(0, self.tokens_before - self.tokens_after)

    @property
    def reduction_pct(self) -> float:
        if self.tokens_before <= 0:
            return 0.0
        return round(100.0 * self.tokens_saved / self.tokens_before, 2)


def compress_abstract(
    query: str,
    abstract: str,
    *,
    top_n: int = DEFAULT_TOP_N,
    secondary_query: str | None = None,
) -> CompressionResult:
    """Scores each sentence of `abstract` by token overlap with `query`
    (and `secondary_query`, if given -- mirrors RetrievalPort.search's
    secondary_query parameter), keeps the top-N highest scoring sentences
    *in their original order* (so citation-marker alignment against the
    source abstract stays sane), and returns the compressed text plus
    before/after token counts.

    Degrades to the full, uncompressed abstract when there are fewer than
    `_MIN_SENTENCES_TO_COMPRESS` sentences to start with -- trimming a
    2-sentence abstract down to N=4 sentences isn't compression, it's a
    no-op with extra bookkeeping, and trimming it to fewer sentences than
    it has risks losing the one sentence a citation actually depends on.
    """
    tokens_before = estimate_tokens(abstract)
    sentences = split_sentences(abstract)

    if len(sentences) < _MIN_SENTENCES_TO_COMPRESS or len(sentences) <= top_n:
        return CompressionResult(
            text=abstract,
            sentences_kept=len(sentences),
            sentences_total=len(sentences),
            tokens_before=tokens_before,
            tokens_after=tokens_before,
            skipped=True,
        )

    query_tokens = _tokenize(query)
    if secondary_query:
        query_tokens |= _tokenize(secondary_query)

    scored = [(_overlap_score(query_tokens, s), i, s) for i, s in enumerate(sentences)]
    # Highest score first; stable tie-break on original order via index i.
    top = sorted(scored, key=lambda t: (-t[0], t[1]))[:top_n]
    # Restore original reading order among the kept sentences.
    kept = [s for _, _, s in sorted(top, key=lambda t: t[1])]
    compressed_text = " ".join(kept)
    tokens_after = estimate_tokens(compressed_text)

    return CompressionResult(
        text=compressed_text,
        sentences_kept=len(kept),
        sentences_total=len(sentences),
        tokens_before=tokens_before,
        tokens_after=tokens_after,
        skipped=False,
    )


@dataclass(frozen=True)
class PaperCompression:
    pmid: str
    result: CompressionResult


def compress_papers_for_prompt(
    query: str,
    papers: list[tuple[str, str]],  # (pmid, abstract) pairs, in prompt order
    *,
    top_n: int = DEFAULT_TOP_N,
    secondary_query: str | None = None,
) -> list[PaperCompression]:
    """Batch entry point intended for the `summary` / `citation_check`
    prompt-assembly call sites: compresses each paper's abstract
    independently (so multiple papers' compressed sentences, once
    concatenated by the caller into a single prompt, never cross-contaminate
    -- each PaperCompression's `result.text` stays scoped to its own pmid)
    and preserves input order so citation markers (e.g. "[pmid]") that a
    caller attaches per-paper stay aligned to the right compressed text.
    """
    out: list[PaperCompression] = []
    for pmid, abstract in papers:
        result = compress_abstract(query, abstract, top_n=top_n, secondary_query=secondary_query)
        out.append(PaperCompression(pmid=pmid, result=result))
    return out


def aggregate_reduction_pct(results: list[CompressionResult]) -> float:
    """Overall token-reduction % across a batch of CompressionResults,
    weighted by tokens_before (not a plain average of per-paper %ages) --
    used by backend/measurement to report one real number for a gold-set
    run rather than an average-of-averages.
    """
    total_before = sum(r.tokens_before for r in results)
    if total_before <= 0:
        return 0.0
    total_after = sum(r.tokens_after for r in results)
    return round(100.0 * (total_before - total_after) / total_before, 2)
