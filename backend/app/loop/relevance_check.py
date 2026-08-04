"""Structured relevance self-check: returns {relevant: bool, confidence:
float}, not free text, so the loop's pass/fail decision is deterministic
and reproducible for a demo recording (plan.md Step 4.2).
"""
from __future__ import annotations

import json

from backend.app.llm_client import ParitokLLMClient

RELEVANCE_SYSTEM_PROMPT = (
    "You are a medical literature relevance evaluator. Assess whether the abstract "
    "is relevant to the query. Return ONLY valid JSON with exactly these keys: "
    '{"relevant": <bool>, "confidence": <float between 0 and 1>}'
)

RELEVANCE_BATCH_SYSTEM_PROMPT = (
    "You are a medical literature relevance evaluator. Assess whether each abstract "
    "is relevant to the query. Return ONLY valid JSON in this exact format: "
    '{"results": [{"pmid": "<pmid>", "relevant": <bool>, "confidence": <float between 0 and 1>}, ...]}'
)


def build_relevance_check_prompt(query: str, abstract: str) -> list[dict]:
    return [
        {"role": "system", "content": RELEVANCE_SYSTEM_PROMPT},
        {"role": "user", "content": f'Query: "{query}"\n\nAbstract: "{abstract}"'},
    ]


def build_relevance_check_batch_prompt(query: str, papers: list[dict]) -> list[dict]:
    abstracts_text = "\n\n".join(
        f'PMID {p["pmid"]}: {p["title"]}\n{p["abstract"]}'
        for p in papers
    )
    return [
        {"role": "system", "content": RELEVANCE_BATCH_SYSTEM_PROMPT},
        {"role": "user", "content": f'Query: "{query}"\n\nAbstracts:\n{abstracts_text}'},
    ]


def run_relevance_check(client: ParitokLLMClient, query: str, abstract: str, *, direct: bool = False) -> dict:
    result = client.chat(
        build_relevance_check_prompt(query, abstract),
        response_format={"type": "json_object"},
        direct=direct,
    )
    if result.degraded:
        return {"relevant": False, "confidence": 0.0}
    try:
        parsed = json.loads(result.content)
    except json.JSONDecodeError:
        return {"relevant": False, "confidence": 0.0}
    return {"relevant": bool(parsed.get("relevant")), "confidence": float(parsed.get("confidence", 0.0))}


def run_relevance_check_batch(client: ParitokLLMClient, query: str, papers: list[dict], *, direct: bool = False) -> dict:
    """Batch relevance check for multiple papers. Returns a dict with 'results' key
    mapping pmid -> {'relevant': bool, 'confidence': float}."""
    if not papers:
        return {"results": {}}

    result = client.chat(
        build_relevance_check_batch_prompt(query, papers),
        response_format={"type": "json_object"},
        direct=direct,
    )

    if result.degraded:
        return {"results": {p["pmid"]: {"relevant": False, "confidence": 0.0} for p in papers}}

    try:
        parsed = json.loads(result.content)
        results_list = parsed.get("results", [])
        # Convert list to pmid-keyed dict for easier lookup
        results_dict = {}
        for item in results_list:
            pmid = item.get("pmid", "")
            if pmid:
                results_dict[pmid] = {
                    "relevant": bool(item.get("relevant", False)),
                    "confidence": float(item.get("confidence", 0.0))
                }
        return {"results": results_dict}
    except (json.JSONDecodeError, TypeError):
        return {"results": {p["pmid"]: {"relevant": False, "confidence": 0.0} for p in papers}}
