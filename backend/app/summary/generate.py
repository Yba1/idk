"""Sourced summary generation (plan.md Step 4.3): every claim links back to
its source paper via a [N] marker matching the numbered abstracts stuffed
into the prompt, so a reader can verify each sentence against its citation.
"""
from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field

from backend.app.llm.json_repair import try_parse_json
from backend.app.llm.tokenizer import estimate_tokens
from backend.contracts.ports import LLMPort


@dataclass
class SourcedSummary:
    text: str
    citations: list[dict]
    raw_text: str = ""
    degraded: bool = False
    original_tokens: int = 0
    compressed_tokens: int = 0
    imaging_findings: str | None = None
    teaching_point: str | None = None
    differential_candidates: list[dict] = field(default_factory=list)


def _build_prompt(query: str, papers: list[dict]) -> tuple[list[dict], int, int]:
    stuffed = "\n\n".join(
        f"[{i+1}] PMID {p['pmid']} - {p['title']}\n{p['abstract']}"
        for i, p in enumerate(papers)
    )
    # v2 has no prompt compression (the v1 Paritok compression path was
    # removed along with llm_client.py) - token counts below reflect the
    # uncompressed prompt on both sides for backward-compatible field shape.
    compressed_stuffed = stuffed
    original_tokens = compressed_tokens = estimate_tokens(stuffed)
    messages = [
        {"role": "system", "content": (
            "You are summarizing rare-case PET/neuroimaging literature for research purposes, "
            "not providing medical advice or diagnosis. Every claim must cite its source using "
            "[N] matching the numbered abstracts below. Do not state or imply a diagnosis for any "
            "individual patient. If a specific detail (tracer dose, timing, modality parameter, etc.) "
            "is not present in the retrieved abstracts, state 'not reported in retrieved abstracts' "
            "rather than omitting it or filling it in from general knowledge.\n\n"
            "Return ONLY a valid JSON object in this exact format:\n"
            '{"summary": "... same citation and abstention rules as above ...", '
            '"imaging_findings": "region + uptake pattern, or null if not stated in the abstracts", '
            '"teaching_point": "1-2 sentence closing point, or null if imaging_findings is null", '
            '"differential": [{"condition_name": "...", "marker": "[2]"}]}\n\n'
            "differential is 0-3 items. Only include an entry when a specific [N] abstract "
            "genuinely supports it as an alternate condition, matching the same citation "
            "discipline used for the summary itself."
        )},
        {"role": "user", "content": f"Query: {query}\n\nRetrieved abstracts:\n{compressed_stuffed}"},
    ]
    return messages, original_tokens, compressed_tokens


LOW_CONFIDENCE_DISCLAIMER = (
    "Note: the search loop's own relevance check did not confirm a strong match for this "
    "query, so the literature below may not be a close fit. Read the following summary with "
    "that in mind.\n\n"
)

SPARSE_COVERAGE_NOTE = (
    "Note: our literature coverage for this condition is limited (fewer than 10 papers in the corpus). "
    "The summary below reflects what is available, but a broader search of PubMed is recommended for "
    "a complete picture.\n\n"
)


def _valid_differential_item(item: dict) -> bool:
    name, marker = item.get("condition_name"), item.get("marker")
    return (
        isinstance(name, str) and name.strip()
        and isinstance(marker, str) and bool(re.match(r"^\[\d+\]$", marker.strip()))
    )


def generate_sourced_summary(
    client: LLMPort,
    query: str,
    papers: list[dict],
    *,
    request_id: str,
    session_id: str,
    user_id: str,
    low_confidence: bool = False,
    sparse_coverage: bool = False,
    on_stage: Callable[[str, dict], None] | None = None,
) -> SourcedSummary:
    if not papers:
        return SourcedSummary(text="", citations=[], raw_text="", degraded=False)

    if on_stage:
        on_stage("compress", {})
    messages, original_tokens, compressed_tokens = _build_prompt(query, papers)
    if on_stage:
        on_stage("summarize", {})
    result = client.chat(
        messages,
        call_site="summary",
        request_id=request_id,
        session_id=session_id,
        user_id=user_id,
    )
    if result.degraded:
        return SourcedSummary(text="", citations=[], raw_text="", degraded=True,
                               original_tokens=original_tokens, compressed_tokens=compressed_tokens)

    parsed = try_parse_json(result.content)
    try:
        summary_text = parsed["summary"]
        if not isinstance(summary_text, str) or not summary_text.strip():
            raise ValueError("summary field missing or empty")
    except (KeyError, ValueError, TypeError):
        return SourcedSummary(text="", citations=[], raw_text="", degraded=True,
                               original_tokens=original_tokens, compressed_tokens=compressed_tokens)

    imaging_findings = parsed.get("imaging_findings")
    if not isinstance(imaging_findings, str) or not imaging_findings.strip():
        imaging_findings = None

    teaching_point = parsed.get("teaching_point")
    if not isinstance(teaching_point, str) or not teaching_point.strip():
        teaching_point = None

    differential_candidates = [
        item for item in parsed.get("differential", []) if isinstance(item, dict) and _valid_differential_item(item)
    ]

    citations = [
        {"marker": f"[{i+1}]", "pmid": p["pmid"], "title": p["title"]}
        for i, p in enumerate(papers)
    ]

    # Choose disclaimer based on condition
    if sparse_coverage:
        text = SPARSE_COVERAGE_NOTE + summary_text
    elif low_confidence:
        text = LOW_CONFIDENCE_DISCLAIMER + summary_text
    else:
        text = summary_text

    return SourcedSummary(text=text, citations=citations, raw_text=summary_text, degraded=False,
                           original_tokens=original_tokens, compressed_tokens=compressed_tokens,
                           imaging_findings=imaging_findings, teaching_point=teaching_point,
                           differential_candidates=differential_candidates)
