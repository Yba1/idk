"""Sourced summary generation: every claim cites its source paper via a [N]
marker matching the numbered abstracts stuffed into the prompt, so a reader
can verify each sentence against its citation.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from backend.app.llm.json_repair import try_parse_json
from backend.contracts.models import Message, ScoredPaper
from backend.contracts.ports import LLMPort

SUMMARY_JSON_SCHEMA = {
    "type": "object",
    "properties": {"summary_markdown": {"type": "string"}},
    "required": ["summary_markdown"],
}

SUMMARY_SYSTEM_PROMPT = (
    "You are summarizing rare-case PET/neuroimaging literature for research purposes, "
    "not providing medical advice or diagnosis. Every claim must cite its source using "
    "[N] matching the numbered abstracts below. Do not state or imply a diagnosis for any "
    "individual patient. If a specific detail is not present in the retrieved abstracts, "
    "state 'not reported in retrieved abstracts' rather than omitting it or filling it in "
    "from general knowledge.\n\n"
    'Return ONLY valid JSON: {"summary_markdown": "<markdown summary, every sentence '
    'carrying a [N] citation>"}'
)


@dataclass
class SourcedCitation:
    index: int
    pmid: str
    supported: bool | None = None
    note: str | None = None


@dataclass
class SourcedSummary:
    markdown: str
    citations: list[SourcedCitation] = field(default_factory=list)
    degraded: bool = False


def _build_messages(query: str, papers: list[ScoredPaper], distilled_context: str) -> list[Message]:
    stuffed = "\n\n".join(
        f"[{i + 1}] PMID {sp.paper.pmid} - {sp.paper.title}\n{sp.paper.abstract}"
        for i, sp in enumerate(papers)
    )
    messages: list[Message] = []
    if distilled_context:
        messages.append(Message(role="system", content=(
            f"The reader is described as: {distilled_context}. Assume familiarity with "
            "material they have already explored; prioritize what is new to them. Do not "
            "mention this description in your answer."
        )))
    messages.append(Message(role="system", content=SUMMARY_SYSTEM_PROMPT))
    messages.append(Message(role="user", content=f"Query: {query}\n\nRetrieved abstracts:\n{stuffed}"))
    return messages


def _extract_citations(markdown: str, papers: list[ScoredPaper]) -> list[SourcedCitation]:
    indices = sorted({int(n) for n in re.findall(r"\[(\d+)\]", markdown)})
    return [
        SourcedCitation(index=i, pmid=papers[i - 1].paper.pmid)
        for i in indices
        if 1 <= i <= len(papers)
    ]


def generate_sourced_summary(
    llm: LLMPort,
    query: str,
    papers: list[ScoredPaper],
    *,
    distilled_context: str = "",
    request_id: str,
    session_id: str,
    user_id: str,
) -> SourcedSummary:
    if not papers:
        return SourcedSummary(markdown="", citations=[], degraded=False)

    result = llm.chat(
        _build_messages(query, papers, distilled_context),
        call_site="summary",
        request_id=request_id,
        session_id=session_id,
        user_id=user_id,
        json_schema=SUMMARY_JSON_SCHEMA,
    )
    if result.degraded:
        return SourcedSummary(markdown="", citations=[], degraded=True)

    # Cortex wraps JSON replies in markdown fences despite "ONLY valid JSON"
    # instructions; try_parse_json handles both raw JSON and fenced JSON
    # (see backend/app/loop/hyde.py and the branch-1 commit 4d894d3 postmortem).
    parsed = try_parse_json(result.content)
    try:
        markdown = parsed["summary_markdown"]
        if not isinstance(markdown, str) or not markdown.strip():
            raise ValueError("summary_markdown missing or empty")
    except (KeyError, ValueError, TypeError):
        return SourcedSummary(markdown="", citations=[], degraded=True)

    return SourcedSummary(markdown=markdown, citations=_extract_citations(markdown, papers), degraded=False)
