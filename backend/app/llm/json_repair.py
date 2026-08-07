"""Structured-output JSON parsing helper for CortexLLMClient.

Cortex COMPLETE's response_format/json_schema option usually returns
parseable JSON, but "usually" is not "always". This module isolates the
parse-then-one-repair-attempt logic so it can be unit tested without a
Snowpark session.
"""
from __future__ import annotations

import json
import re

_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)


def try_parse_json(content: str) -> dict | None:
    """Best-effort parse: raw JSON, then JSON inside a ```...``` fence."""
    if content is None:
        return None
    text = content.strip()
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        pass

    match = _FENCE_RE.search(text)
    if match:
        try:
            return json.loads(match.group(1))
        except (json.JSONDecodeError, TypeError):
            return None
    return None


def build_repair_messages(original_messages: list[dict], bad_content: str, json_schema: dict) -> list[dict]:
    """One repair turn: ask the model to re-emit strictly valid JSON matching
    the schema, given what it produced last time.
    """
    repair_instruction = {
        "role": "user",
        "content": (
            "Your previous reply was not valid JSON matching the required "
            "schema. Reply again with ONLY valid JSON matching this schema, "
            "no prose, no markdown fences.\n\n"
            f"Schema: {json.dumps(json_schema)}\n\n"
            f"Your previous reply:\n{bad_content}"
        ),
    }
    return [*original_messages, repair_instruction]
