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
        prompt_tokens = sum(len(m.content.split()) for m in messages)
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
