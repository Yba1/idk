"""Researcher profile distillation: turns a ResearcherProfile into a <=600
char natural-language paragraph injected into the summary prompt. Regenerated
lazily (only on a query_count multiple-of-3 or a specialty change) since it
is the one LLM call this feature adds to the hot path.
"""
from __future__ import annotations

import json
import re

from backend.contracts.models import Message, ResearcherProfile
from backend.contracts.ports import LLMPort

MAX_DISTILLED_CONTEXT_CHARS = 600

DISTILL_JSON_SCHEMA = {
    "type": "object",
    "properties": {"distilled_context": {"type": "string"}},
    "required": ["distilled_context"],
}

DISTILL_SYSTEM_PROMPT = (
    "Summarize this researcher's profile in at most a few sentences for injection into "
    "another prompt: their specialty, the conditions they have explored so far, and the "
    "apparent depth of their prior engagement. Do not include PMIDs, patient-like details, "
    "or verbatim query text. "
    'Return ONLY valid JSON: {"distilled_context": "<the paragraph, under 600 characters>"}'
)

_PMID_PATTERN = re.compile(r"\bPMID\s*:?\s*\d+\b", re.IGNORECASE)


def should_distill(query_count: int, *, specialty_changed: bool) -> bool:
    if specialty_changed:
        return True
    return query_count > 0 and query_count % 3 == 0


def build_distill_messages(profile: ResearcherProfile) -> list[Message]:
    facts = (
        f"specialty: {profile.specialty or 'unspecified'}\n"
        f"conditions explored: {', '.join(profile.conditions_explored) or 'none yet'}\n"
        f"query count: {profile.query_count}"
    )
    return [
        Message(role="system", content=DISTILL_SYSTEM_PROMPT),
        Message(role="user", content=facts),
    ]


def distill_profile(
    llm: LLMPort, profile: ResearcherProfile, *, request_id: str, session_id: str, user_id: str
) -> str:
    """Returns the new distilled_context, or the profile's existing one on any
    failure (never destroys a good value on a bad call).
    """
    result = llm.chat(
        build_distill_messages(profile),
        call_site="memory_distill",
        request_id=request_id,
        session_id=session_id,
        user_id=user_id,
        json_schema=DISTILL_JSON_SCHEMA,
    )
    if result.degraded:
        return profile.distilled_context
    try:
        text = json.loads(result.content).get("distilled_context", "")
    except (json.JSONDecodeError, AttributeError):
        return profile.distilled_context
    if not isinstance(text, str) or not text.strip():
        return profile.distilled_context
    return _sanitize(text)[:MAX_DISTILLED_CONTEXT_CHARS]


def _sanitize(text: str) -> str:
    return _PMID_PATTERN.sub("[citation omitted]", text).strip()
