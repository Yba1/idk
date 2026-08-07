"""FROZEN at tag contracts-v1. Do not edit on a feature branch.

Deterministic in-process implementations of all four ports, backed by
backend/data/corpus.json and canned LLM responses keyed by call_site. These
let every lane build against the "fake" profile in config/services.yaml from
minute zero, with zero credentials in the environment.
"""
from __future__ import annotations

import functools
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Sequence

from backend.contracts.models import (
    CallSite,
    ChatResult,
    ConditionMatch,
    LedgerEvent,
    Message,
    Paper,
    ResearcherProfile,
    ScoredPaper,
    SessionThread,
    TokenUsage,
)

_CORPUS_PATH = Path(__file__).resolve().parent.parent / "data" / "corpus.json"
RARE_BOOST = 1.6
COMMON_BOOST = 1.0

_WORD_RE = re.compile(r"[a-z0-9]+")


def _tokenize(text: str) -> set[str]:
    return set(_WORD_RE.findall(text.lower()))


@functools.lru_cache(maxsize=1)
def _load_corpus() -> list[Paper]:
    with open(_CORPUS_PATH) as fh:
        raw = json.load(fh)
    papers = []
    for row in raw:
        papers.append(
            Paper(
                pmid=row["pmid"],
                title=row["title"],
                abstract=row["abstract"],
                journal=row.get("journal", ""),
                year=row.get("year", 0),
                condition=row["condition"],
                is_rare=row.get("rarity") == "rare",
                url=row.get("url", f"https://pubmed.ncbi.nlm.nih.gov/{row['pmid']}/"),
            )
        )
    return papers


class FakeRetrieval:
    """Naive token-overlap scoring over the corpus JSON. Deterministic."""

    def search(
        self,
        query: str,
        *,
        secondary_query: str | None = None,
        top_k: int = 10,
        apply_rarity: bool = True,
        exclude_pmids: Sequence[str] = (),
    ) -> list[ScoredPaper]:
        query_tokens = _tokenize(query)
        if secondary_query:
            query_tokens |= _tokenize(secondary_query)

        excluded = set(exclude_pmids)
        scored: list[ScoredPaper] = []
        for paper in _load_corpus():
            if paper.pmid in excluded:
                continue
            paper_tokens = _tokenize(paper.title) | _tokenize(paper.abstract)
            lexical_score = float(len(query_tokens & paper_tokens))
            rarity_multiplier = RARE_BOOST if paper.is_rare else COMMON_BOOST
            score = lexical_score * rarity_multiplier if apply_rarity else lexical_score
            scored.append(
                ScoredPaper(
                    paper=paper,
                    score=score,
                    lexical_score=lexical_score,
                    semantic_score=0.0,
                    rarity_multiplier=rarity_multiplier if apply_rarity else 1.0,
                )
            )

        scored.sort(key=lambda sp: (sp.score, sp.paper.pmid), reverse=True)
        return scored[:top_k]

    def closest_conditions(self, query: str, top_n: int = 3) -> list[ConditionMatch]:
        query_tokens = _tokenize(query)
        by_condition: dict[str, list[Paper]] = defaultdict(list)
        for paper in _load_corpus():
            by_condition[paper.condition].append(paper)

        matches: list[ConditionMatch] = []
        for condition, papers in by_condition.items():
            condition_tokens: set[str] = set()
            for paper in papers:
                condition_tokens |= _tokenize(paper.title) | _tokenize(paper.abstract)
            union = query_tokens | condition_tokens
            similarity = len(query_tokens & condition_tokens) / len(union) if union else 0.0
            matches.append(
                ConditionMatch(
                    condition=condition,
                    similarity=similarity,
                    paper_count=len(papers),
                    is_rare=papers[0].is_rare,
                )
            )

        matches.sort(key=lambda m: (m.similarity, m.condition), reverse=True)
        return matches[:top_n]

    def get_by_pmids(self, pmids: Sequence[str]) -> list[Paper]:
        wanted = set(pmids)
        return [p for p in _load_corpus() if p.pmid in wanted]

    def health(self) -> dict:
        return {"ok": True, "detail": f"fake retrieval, {len(_load_corpus())} papers"}


_CANNED_CONTENT: dict[CallSite, str] = {
    "hyde": json.dumps({"expanded_query": "fake expanded query for hyde"}),
    "relevance_check": json.dumps({"relevant": True, "confidence": 0.75, "note": "fake relevance note"}),
    "refine": json.dumps({"refined_query": "fake refined query"}),
    "summary": json.dumps({"summary_markdown": "**Fake summary.**", "citations": []}),
    "citation_check": json.dumps({"supported": True, "note": None}),
    "memory_distill": json.dumps({"distilled_context": "fake distilled researcher context"}),
}

# --- Extractive stand-in for the `summary` call site ------------------------
#
# The canned "**Fake summary.**" above is fine for assertions but useless for
# looking at: §03 renders a literal placeholder and "Claims traced 0 / 0",
# which says nothing true about the product.
#
# This builds a summary the honest way instead of inventing prose: it parses
# the numbered abstracts out of the prompt the pipeline actually sent, picks
# the sentence from each that best overlaps the query, and emits it carrying
# that paper's real [N] marker. So every sentence on screen is a verbatim
# sentence from a real PubMed abstract that was really retrieved for that
# query, and every citation resolves to that paper's real PMID.
#
# It is a deterministic local extractor, NOT a language model, and it is not
# pretending to be one -- with Snowflake credentials configured this call site
# goes to Cortex COMPLETE and this code never runs. Say exactly that if anyone
# asks what generated it.

def _role_of(message) -> str:
    """Call sites build plain dicts in some paths and Message dataclasses in
    others (CortexLLMClient.chat accepts either); mirror that tolerance."""
    return message.get("role", "") if isinstance(message, dict) else getattr(message, "role", "")


def _content_of(message) -> str:
    return message.get("content", "") if isinstance(message, dict) else getattr(message, "content", "")


_PROMPT_PAPER_RE = re.compile(
    r"\[(\d+)\]\s+PMID\s+(\S+)\s+-\s+(.+?)\n(.*?)(?=\n\n\[\d+\]\s+PMID|\Z)",
    re.DOTALL,
)
# Split on sentence-final punctuation followed by whitespace, without
# requiring the next character to be [A-Z0-9]: PubMed abstracts routinely open
# sentences with a superscript tracer name ("¹⁸F-FDG PET showed..."), and the
# stricter lookahead silently glued four sentences into one.
_SENT_SPLIT_RE = re.compile(r"(?<=[.!?])\s+(?=[^\s a-z])")
_MAX_SUMMARY_CLAIMS = 4
# Keep each claim to one readable line on screen. Sentences longer than this
# are skipped in favour of the next-best candidate rather than truncated --
# a half-sentence carrying a [N] marker would be a claim nobody actually made.
_MAX_CLAIM_CHARS = 240


def _extractive_summary(messages: list[Message]) -> str | None:
    """Return a `summary` JSON payload built from the prompt's own abstracts,
    or None if the prompt isn't in the expected shape (caller falls back to
    the canned payload rather than guessing).
    """
    user = next((m for m in reversed(messages) if _role_of(m) == "user"), None)
    if user is None:
        return None
    content = _content_of(user)

    query = ""
    if content.startswith("Query:"):
        query = content.split("\n", 1)[0][len("Query:"):].strip()
    query_tokens = _tokenize(query)

    papers = _PROMPT_PAPER_RE.findall(content)
    if not papers:
        return None

    sentences: list[str] = []
    seen_pmids: set[str] = set()
    seen_sentences: set[str] = set()
    for index, pmid, title, abstract in papers:
        if len(sentences) >= _MAX_SUMMARY_CLAIMS:
            break
        # The corpus contains near-duplicate records (the same PMID retrieved
        # twice), which would otherwise render as the same sentence cited to
        # two different [N] markers -- the exact thing a citation-verification
        # product must not do.
        if pmid in seen_pmids:
            continue
        candidates = [s.strip() for s in _SENT_SPLIT_RE.split(abstract.strip()) if s.strip()]
        short = [s for s in candidates if len(s) <= _MAX_CLAIM_CHARS]
        candidates = [s for s in (short or candidates) if s not in seen_sentences]
        if not candidates:
            candidates = [title.strip()]
        best = max(candidates, key=lambda s: len(query_tokens & _tokenize(s)))
        seen_pmids.add(pmid)
        seen_sentences.add(best)
        best = best.rstrip().rstrip(".!?")
        # Marker sits INSIDE the sentence, before the terminal period. The
        # frontend splits on /(?<=[.!?])\s+(?=[A-Z0-9])/, so a marker placed
        # after the period ("text. [N] Next...") blocks the split and collapses
        # every claim into one mis-attributed block.
        sentences.append(f"{best} [{index}].")

    if not sentences:
        return None

    markdown = " ".join(sentences)
    return json.dumps({"summary_markdown": markdown})


_CLAIMS_BLOCK_RE = re.compile(r"Claims to verify:\s*(\[.*?\])\s*\n\nFor each", re.DOTALL)
_SUMMARY_BLOCK_RE = re.compile(r"\nSummary:\n(.*?)\n\nClaims to verify:", re.DOTALL)
# A claim is "supported" when most of its content words actually occur in the
# abstract it cites. Stand-in for the judge model's semantic check -- crude,
# but it is a real comparison of the claim against its source, not a rubber
# stamp, so an [N] pointing at the wrong paper is still caught.
_SUPPORT_THRESHOLD = 0.6


def _per_claim_citation_verdicts(messages: list[Message]) -> str | None:
    """Return a `citation_check` JSON payload with one verdict per claim, or
    None if the prompt isn't in the expected shape."""
    user = next((m for m in reversed(messages) if _role_of(m) == "user"), None)
    if user is None:
        return None
    content = _content_of(user)

    claims_match = _CLAIMS_BLOCK_RE.search(content)
    summary_match = _SUMMARY_BLOCK_RE.search(content)
    if not claims_match or not summary_match:
        return None
    try:
        claims = json.loads(claims_match.group(1))
    except json.JSONDecodeError:
        return None
    if not isinstance(claims, list) or not claims:
        return None

    summary = summary_match.group(1)
    results = []
    for claim in claims:
        if not isinstance(claim, dict) or "index" not in claim:
            continue
        index = claim["index"]
        sentence = next(
            (s for s in _SENT_SPLIT_RE.split(summary) if f"[{index}]" in s),
            "",
        )
        claim_tokens = _tokenize(re.sub(r"\[\d+\]", " ", sentence))
        abstract_tokens = _tokenize(str(claim.get("abstract", "")))
        if not claim_tokens:
            continue
        overlap = len(claim_tokens & abstract_tokens) / len(claim_tokens)
        supported = overlap >= _SUPPORT_THRESHOLD
        results.append({
            "index": index,
            "supported": supported,
            "note": (
                "Sentence occurs in the cited abstract."
                if supported
                else "Claim wording not found in the cited abstract."
            ),
        })

    return json.dumps({"results": results}) if results else None


class FakeLLM:
    """Canned per-call_site JSON payloads. Records to the active ledger."""

    def chat(
        self,
        messages: list[Message],
        *,
        call_site: CallSite,
        request_id: str,
        session_id: str,
        user_id: str,
        json_schema: dict | None = None,
        max_output_tokens: int = 1024,
    ) -> ChatResult:
        content = _CANNED_CONTENT.get(call_site, json.dumps({}))

        # For the two call sites whose output is rendered to a human, derive a
        # real payload from the prompt instead of returning the placeholder.
        # Both fall back to the canned string if the prompt isn't in the shape
        # they expect, so no assertion that depends on the canned value breaks
        # unless the pipeline genuinely sent real papers.
        if call_site == "summary":
            content = _extractive_summary(messages) or content
        elif call_site == "citation_check":
            content = _per_claim_citation_verdicts(messages) or content

        prompt_tokens = sum(len(_content_of(m).split()) for m in messages)
        completion_tokens = len(content.split())
        usage = TokenUsage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            model="fake",
            cost_usd=round((prompt_tokens + completion_tokens) * 0.000002, 8),
        )

        from backend.contracts.registry import get_services
        import datetime

        get_services().ledger.record(
            LedgerEvent(
                request_id=request_id,
                session_id=session_id,
                user_id=user_id,
                call_site=call_site,
                usage=usage,
                latency_ms=0,
                degraded=False,
                occurred_at_iso=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            )
        )
        return ChatResult(content=content, usage=usage, degraded=False, error=None)

    def health(self) -> dict:
        return {"ok": True, "detail": "fake llm"}


class FakeMemory:
    """Process-local dict-backed memory."""

    def __init__(self) -> None:
        self._profiles: dict[str, ResearcherProfile] = {}
        self._threads: dict[tuple[str, str], SessionThread] = {}
        self._seen: dict[str, set[str]] = defaultdict(set)

    def get_profile(self, user_id: str) -> ResearcherProfile:
        return self._profiles.get(user_id, ResearcherProfile(user_id=user_id, specialty=None))

    def get_thread(self, user_id: str, session_id: str) -> SessionThread:
        return self._threads.get(
            (user_id, session_id), SessionThread(session_id=session_id, user_id=user_id)
        )

    def record_query(self, user_id: str, session_id: str, query: str,
                     matched_conditions: Sequence[str]) -> None:
        thread = self.get_thread(user_id, session_id)
        self._threads[(user_id, session_id)] = SessionThread(
            session_id=session_id,
            user_id=user_id,
            queries=[*thread.queries, query],
            pmids_shown=thread.pmids_shown,
        )
        profile = self.get_profile(user_id)
        conditions_explored = list(profile.conditions_explored)
        for c in matched_conditions:
            if c not in conditions_explored:
                conditions_explored.append(c)
        self._profiles[user_id] = ResearcherProfile(
            user_id=user_id,
            specialty=profile.specialty,
            conditions_explored=conditions_explored,
            query_count=profile.query_count + 1,
            distilled_context=profile.distilled_context,
        )

    def record_papers_shown(self, user_id: str, session_id: str,
                            pmids: Sequence[str]) -> None:
        thread = self.get_thread(user_id, session_id)
        self._threads[(user_id, session_id)] = SessionThread(
            session_id=session_id,
            user_id=user_id,
            queries=thread.queries,
            pmids_shown=[*thread.pmids_shown, *pmids],
        )
        self._seen[user_id] |= set(pmids)

    def seen_pmids(self, user_id: str) -> set[str]:
        return set(self._seen.get(user_id, set()))

    def set_specialty(self, user_id: str, specialty: str) -> None:
        profile = self.get_profile(user_id)
        self._profiles[user_id] = ResearcherProfile(
            user_id=user_id,
            specialty=specialty,
            conditions_explored=profile.conditions_explored,
            query_count=profile.query_count,
            distilled_context=profile.distilled_context,
        )

    def forget(self, user_id: str) -> None:
        self._profiles.pop(user_id, None)
        self._seen.pop(user_id, None)
        for key in [k for k in self._threads if k[0] == user_id]:
            self._threads.pop(key, None)

    def health(self) -> dict:
        return {"ok": True, "detail": "fake memory"}


class FakeLedger:
    """Appends to an in-memory list exposed as .events."""

    def __init__(self) -> None:
        self.events: list[LedgerEvent] = []

    def record(self, event: LedgerEvent) -> None:
        self.events.append(event)

    def health(self) -> dict:
        return {"ok": True, "detail": f"fake ledger, {len(self.events)} events"}
