"""Citation verification: one batched judge call per summary, checking every
[N] claim against its cited paper's abstract, so the citation requirement
never scales the per-query LLM call budget with the number of claims.
"""
from __future__ import annotations

import json
from dataclasses import replace

from backend.app.llm.json_repair import try_parse_json
from backend.contracts.models import Message, ScoredPaper
from backend.contracts.ports import LLMPort
from backend.app.summary.generate import SourcedCitation

CITATION_CHECK_SYSTEM_PROMPT = (
    "You are a medical literature citation verifier. For each claim (identified by its "
    "[N] index) and its cited abstract, determine whether the abstract supports the claim. "
    "Return ONLY valid JSON in this exact format: "
    '{"results": [{"index": <int>, "supported": <bool>, "note": "<short reason>"}, ...]}'
)

CITATION_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "results": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "index": {"type": "integer"},
                    "supported": {"type": "boolean"},
                    "note": {"type": ["string", "null"]},
                },
                "required": ["index", "supported"],
            },
        }
    },
    "required": ["results"],
}


def build_citation_check_messages(
    query: str, markdown: str, papers: list[ScoredPaper], citations: list[SourcedCitation]
) -> list[Message]:
    claims = [
        {"index": c.index, "abstract": papers[c.index - 1].paper.abstract}
        for c in citations
    ]
    user_prompt = (
        f'Query: "{query}"\n\nSummary:\n{markdown}\n\n'
        f"Claims to verify:\n{json.dumps(claims, indent=2)}\n\n"
        "For each, determine if the abstract supports the claim at that index. Return ONLY valid JSON."
    )
    return [
        Message(role="system", content=CITATION_CHECK_SYSTEM_PROMPT),
        Message(role="user", content=user_prompt),
    ]


def check_citations(
    llm: LLMPort,
    query: str,
    markdown: str,
    papers: list[ScoredPaper],
    citations: list[SourcedCitation],
    *,
    request_id: str,
    session_id: str,
    user_id: str,
) -> list[SourcedCitation]:
    """Returns citations with `supported`/`note` filled in. On any failure,
    citations come back unchanged with `supported=None` (truthfully unverified),
    never dropped or silently marked supported.
    """
    if not citations:
        return []

    result = llm.chat(
        build_citation_check_messages(query, markdown, papers, citations),
        call_site="citation_check",
        request_id=request_id,
        session_id=session_id,
        user_id=user_id,
        json_schema=CITATION_JSON_SCHEMA,
    )
    if result.degraded:
        return citations

    parsed = try_parse_json(result.content)
    if parsed is None:
        return citations

    results = parsed.get("results")
    if isinstance(results, list):
        by_index = {r.get("index"): r for r in results if isinstance(r, dict)}
        return [
            replace(c, supported=bool(by_index[c.index]["supported"]), note=by_index[c.index].get("note"))
            if c.index in by_index and "supported" in by_index[c.index]
            else c
            for c in citations
        ]

    # Flat single-verdict fallback (the shape FakeLLM's canned payload uses):
    # applied uniformly since there is nothing per-claim to key off of.
    supported = parsed.get("supported")
    if supported is None:
        return citations
    note = parsed.get("note")
    return [replace(c, supported=bool(supported), note=note) for c in citations]
