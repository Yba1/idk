"""Structured relevance self-check for one search-loop round: judges the
retrieved batch as a whole and returns {relevant, confidence, note}, not free
text, so the loop's pass/fail decision is deterministic.
"""
from __future__ import annotations

from backend.app.llm.json_repair import try_parse_json
from backend.contracts.models import Message, ScoredPaper
from backend.contracts.ports import LLMPort

RELEVANCE_SYSTEM_PROMPT = (
    "You are a medical literature relevance evaluator. Assess whether the retrieved "
    "abstracts, as a set, are relevant to the query. Return ONLY valid JSON with exactly "
    'these keys: {"relevant": <bool>, "confidence": <float between 0 and 1>, "note": "<short note>"}'
)

RELEVANCE_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "relevant": {"type": "boolean"},
        "confidence": {"type": "number"},
        "note": {"type": "string"},
    },
    "required": ["relevant", "confidence"],
}


def build_relevance_messages(query: str, papers: list[ScoredPaper]) -> list[Message]:
    abstracts_text = "\n\n".join(
        f"PMID {sp.paper.pmid}: {sp.paper.title}\n{sp.paper.abstract}" for sp in papers
    )
    return [
        Message(role="system", content=RELEVANCE_SYSTEM_PROMPT),
        Message(role="user", content=f'Query: "{query}"\n\nAbstracts:\n{abstracts_text}'),
    ]


def run_relevance_check(
    llm: LLMPort,
    query: str,
    papers: list[ScoredPaper],
    *,
    request_id: str,
    session_id: str,
    user_id: str,
) -> dict:
    """Returns {"relevant": bool, "confidence": float, "note": str}."""
    if not papers:
        return {"relevant": False, "confidence": 0.0, "note": "no papers retrieved"}

    result = llm.chat(
        build_relevance_messages(query, papers),
        call_site="relevance_check",
        request_id=request_id,
        session_id=session_id,
        user_id=user_id,
        json_schema=RELEVANCE_JSON_SCHEMA,
    )
    if result.degraded:
        return {"relevant": True, "confidence": 0.0, "note": "relevance check degraded; treated as passing"}
    # Cortex wraps JSON replies in markdown fences despite "ONLY valid JSON"
    # instructions; try_parse_json handles both raw JSON and fenced JSON
    # (see branch-1 commit 4d894d3 postmortem).
    parsed = try_parse_json(result.content)
    if parsed is None:
        return {"relevant": True, "confidence": 0.0, "note": "relevance check returned invalid JSON; treated as passing"}
    return {
        "relevant": bool(parsed.get("relevant")),
        "confidence": float(parsed.get("confidence", 0.0)),
        "note": str(parsed.get("note", "")),
    }
