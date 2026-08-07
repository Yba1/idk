"""HyDE (Hypothetical Document Embeddings) query expansion: ask the model to
write a plausible case report for the query, then retrieve against that
hypothetical text instead of the short raw query, since case-report language
matches literature far better than a short symptom description does.
"""
from __future__ import annotations

from backend.app.llm.json_repair import try_parse_json
from backend.contracts.models import Message
from backend.contracts.ports import LLMPort

HYDE_JSON_SCHEMA = {
    "type": "object",
    "properties": {"expanded_query": {"type": "string"}},
    "required": ["expanded_query"],
}


def build_hyde_messages(query: str) -> list[Message]:
    return [
        Message(role="system", content=(
            "You write a short, plausible medical case report abstract (3-5 sentences) "
            "describing a PET/neuroimaging finding matching the user's query. This is used "
            "purely to improve literature retrieval matching, not as medical advice. "
            'Return ONLY valid JSON: {"expanded_query": "<the case report text>"}'
        )),
        Message(role="user", content=f"Query: {query}"),
    ]


def run_hyde(
    llm: LLMPort, query: str, *, request_id: str, session_id: str, user_id: str
) -> str:
    """Returns the expanded query text, falling back to the raw query on any failure."""
    result = llm.chat(
        build_hyde_messages(query),
        call_site="hyde",
        request_id=request_id,
        session_id=session_id,
        user_id=user_id,
        json_schema=HYDE_JSON_SCHEMA,
    )
    if result.degraded:
        return query
    parsed = try_parse_json(result.content)
    expanded = parsed.get("expanded_query") if parsed else None
    return expanded if isinstance(expanded, str) and expanded.strip() else query
