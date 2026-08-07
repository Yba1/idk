"""FROZEN at tag contracts-v1. Do not edit on a feature branch."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Literal

CallSite = Literal[
    "hyde",             # query expansion
    "relevance_check",  # loop gate
    "refine",           # query rewrite
    "summary",          # sourced summary generation
    "citation_check",   # per-claim verification
    "memory_distill",   # EverOS profile summarization
]


@dataclass(frozen=True)
class Paper:
    pmid: str
    title: str
    abstract: str
    journal: str
    year: int
    condition: str
    is_rare: bool
    url: str


@dataclass(frozen=True)
class ScoredPaper:
    paper: Paper
    score: float             # final score after every adjustment
    lexical_score: float     # 0.0 if the backend does not expose it
    semantic_score: float    # 0.0 if the backend does not expose it
    rarity_multiplier: float # 1.0 == no boost applied
    memory_multiplier: float = 1.0  # set only by Card 2A's re-ranker


@dataclass(frozen=True)
class ConditionMatch:
    condition: str
    similarity: float
    paper_count: int
    is_rare: bool


@dataclass(frozen=True)
class Message:
    role: Literal["system", "user", "assistant"]
    content: str


@dataclass(frozen=True)
class TokenUsage:
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    model: str
    cost_usd: float


@dataclass(frozen=True)
class ChatResult:
    content: str
    usage: TokenUsage
    degraded: bool = False
    error: str | None = None


@dataclass(frozen=True)
class LedgerEvent:
    request_id: str
    session_id: str
    user_id: str
    call_site: CallSite
    usage: TokenUsage
    latency_ms: int
    degraded: bool
    occurred_at_iso: str


@dataclass(frozen=True)
class ResearcherProfile:
    user_id: str
    specialty: str | None
    conditions_explored: list[str] = field(default_factory=list)
    query_count: int = 0
    distilled_context: str = ""   # <= 600 chars, injected into summary prompt


@dataclass(frozen=True)
class SessionThread:
    session_id: str
    user_id: str
    queries: list[str] = field(default_factory=list)
    pmids_shown: list[str] = field(default_factory=list)
