"""Self-Query Refinement: rewrite the query using the prior round's
low-confidence reasoning, carried forward so the loop visibly catches and
fixes a bad retrieval rather than just retrying blindly.
"""
from __future__ import annotations

from backend.app.llm.json_repair import try_parse_json
from backend.contracts.models import Message
from backend.contracts.ports import LLMPort

REFINE_JSON_SCHEMA = {
    "type": "object",
    "properties": {"refined_query": {"type": "string"}},
    "required": ["refined_query"],
}


def build_refine_messages(query: str, note: str) -> list[Message]:
    return [
        Message(role="system", content=(
            "Refine the search query given the prior round's low-confidence result. "
            'Return ONLY valid JSON: {"refined_query": "<the refined query text>"}'
        )),
        Message(role="user", content=f"Original query: {query}\nPrior reasoning: {note}"),
    ]


def run_refine(
    llm: LLMPort, query: str, note: str, *, request_id: str, session_id: str, user_id: str
) -> str:
    """Returns the refined query text, falling back to the original query on any failure."""
    result = llm.chat(
        build_refine_messages(query, note),
        call_site="refine",
        request_id=request_id,
        session_id=session_id,
        user_id=user_id,
        json_schema=REFINE_JSON_SCHEMA,
    )
    if result.degraded:
        return query
    # Cortex wraps JSON replies in markdown fences despite "ONLY valid JSON"
    # instructions; try_parse_json handles both raw JSON and fenced JSON
    # (see branch-1 commit 4d894d3 postmortem).
    parsed = try_parse_json(result.content)
    if parsed is None:
        return query
    refined = parsed.get("refined_query")
    return refined if isinstance(refined, str) and refined.strip() else query
