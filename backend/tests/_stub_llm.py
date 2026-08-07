"""Shared LLMPort/ScoredPaper test doubles. Not a test module itself (no
test_ prefix), so pytest never collects it directly.
"""
from __future__ import annotations

from backend.contracts.models import ChatResult, Paper, ScoredPaper, TokenUsage


class StubLLM:
    """Deterministic LLMPort double. `responses` maps call_site -> either a
    fixed JSON string, or a callable(call_number) -> JSON string, so a
    call_site's answer can change across successive rounds (e.g. a
    relevance_check that fails once then passes on retry).
    """

    def __init__(self, responses: dict[str, object], *, degraded_sites: set[str] | None = None):
        self.responses = responses
        self.degraded_sites = degraded_sites or set()
        self.calls: list[tuple[str, list]] = []
        self._call_counts: dict[str, int] = {}

    def chat(self, messages, *, call_site, request_id=None, session_id=None, user_id=None,
              json_schema=None, max_output_tokens=1024) -> ChatResult:
        self.calls.append((call_site, messages))
        self._call_counts[call_site] = self._call_counts.get(call_site, 0) + 1
        degraded = call_site in self.degraded_sites
        content = ""
        if not degraded:
            value = self.responses.get(call_site, "{}")
            content = value(self._call_counts[call_site]) if callable(value) else value
        usage = TokenUsage(prompt_tokens=10, completion_tokens=5, total_tokens=15, model="stub", cost_usd=0.0001)
        return ChatResult(content=content, usage=usage, degraded=degraded, error="stub degraded" if degraded else None)

    def health(self) -> dict:
        return {"ok": True, "detail": "stub"}


def make_scored_paper(
    pmid: str, condition: str = "Test condition", *, is_rare: bool = False, score: float = 1.0
) -> ScoredPaper:
    return ScoredPaper(
        paper=Paper(
            pmid=pmid, title=f"Title {pmid}", abstract="abstract abstract", journal="J",
            year=2020, condition=condition, is_rare=is_rare, url="https://example.com",
        ),
        score=score, lexical_score=score, semantic_score=0.0,
        rarity_multiplier=1.6 if is_rare else 1.0,
    )
