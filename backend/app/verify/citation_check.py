"""Live citation verification: for each [N] claim, judge whether the cited
paper's abstract supports the claim (plan.md Step 5: Citation Verification).
"""
from __future__ import annotations

import json
import re
from collections.abc import Callable

from backend.app.llm_client import ParitokLLMClient


CITATION_CHECK_SYSTEM_PROMPT = (
    "You are a medical literature citation verifier. For each claim and its cited "
    "abstract, determine whether the abstract supports, contradicts, or does not "
    "address the claim. Return ONLY valid JSON in this exact format: "
    '{"results": [{"marker": "[1]", "sentence_index": 0, "status": "supported"|"unsupported", "reason": "<short reason>"}, ...]}'
)

SUPERSCRIPT_DIGITS = str.maketrans("⁰¹²³⁴⁵⁶⁷⁸⁹", "0123456789")

DIFFERENTIAL_CHECK_SYSTEM_PROMPT = (
    "You are a medical literature differential-diagnosis verifier. For each candidate "
    "alternate condition and its cited abstract, determine whether the abstract genuinely "
    "supports that condition as a plausible differential diagnosis. Return ONLY valid JSON "
    "in this exact format: "
    '{"results": [{"condition_name": "...", "marker": "[1]", "status": "supported"|"unsupported", "reason": "<short reason>"}, ...]}'
)


def split_cited_sentences(raw_text: str) -> list[dict]:
    """Split raw_text into sentences, tagging each with any [N] marker(s) found.
    Returns a list of {"sentence": str, "markers": list[str]} - markers is the list
    of literal marker strings found (e.g. ["[1]", "[2]"]), empty list if none."""
    if not raw_text:
        return []

    # Split on sentence boundaries: . ! ? followed by space or end of string
    sentence_pattern = r'(?<=[.!?])\s+'
    raw_sentences = re.split(sentence_pattern, raw_text)

    result = []
    for sentence in raw_sentences:
        if not sentence.strip():
            continue
        # Find all [N] markers in this sentence (the LLM sometimes writes
        # markers with superscript digits, e.g. "[¹]" instead of "[1]")
        markers = re.findall(r'\[\d+\]', sentence.translate(SUPERSCRIPT_DIGITS))
        result.append({"sentence": sentence, "markers": markers})

    return result


def check_citations(
    client: ParitokLLMClient,
    query: str,
    raw_text: str,
    papers: list[dict],
    *,
    on_stage: Callable[[str, dict], None] | None = None,
) -> list[dict]:
    """Verify each cited claim in raw_text against its source paper's abstract.
    Returns a list of {"sentence": str, "marker": str | None, "status": str, "reason": str}.
    status is one of: "supported", "unsupported", "uncited", "invalid_marker", "unverified".
    """
    if not papers or not raw_text:
        return []

    sentences_with_markers = split_cited_sentences(raw_text)
    if not sentences_with_markers:
        return []

    # Step 2 & 3: Separate sentences with no markers (uncited) and invalid markers
    uncited_results = []
    invalid_marker_results = []
    judge_batch = []  # (sentence, marker, abstract) tuples to send to judge

    for sentence_idx, sentence_data in enumerate(sentences_with_markers):
        sentence = sentence_data["sentence"]
        markers = sentence_data["markers"]

        if not markers:
            # No markers -> uncited claim
            uncited_results.append({
                "sentence": sentence,
                "marker": None,
                "status": "uncited",
                "reason": "No citation marker found for this claim."
            })
        else:
            # Check each marker in this sentence
            for marker in markers:
                # Extract the number from [N]
                match = re.match(r'\[(\d+)\]', marker)
                if not match:
                    continue
                marker_num = int(match.group(1))

                # Check if marker is valid (1-indexed, within range)
                if not (1 <= marker_num <= len(papers)):
                    invalid_marker_results.append({
                        "sentence": sentence,
                        "marker": marker,
                        "status": "invalid_marker",
                        "reason": f"Citation {marker} does not match any of the {len(papers)} cited papers."
                    })
                else:
                    # Valid marker -> add to judge batch
                    abstract = papers[marker_num - 1]["abstract"]
                    judge_batch.append((sentence, marker, abstract, sentence_idx))

    # Step 4: If no valid (sentence, marker) pairs, return uncited + invalid results
    if not judge_batch:
        return uncited_results + invalid_marker_results

    # Build the batched judge prompt
    batch_claims = []
    for sentence, marker, abstract, _ in judge_batch:
        batch_claims.append({
            "marker": marker,
            "sentence": sentence,
            "abstract": abstract
        })

    user_prompt = f"""Query: "{query}"

Evaluate each claim-abstract pair below:

{json.dumps(batch_claims, indent=2)}

For each, determine if the abstract supports the claim. Return ONLY valid JSON."""

    messages = [
        {"role": "system", "content": CITATION_CHECK_SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]

    # Step 5: Call the judge with response_format and direct=True
    if on_stage:
        on_stage("citation_check", {})
    result = client.chat(
        messages,
        response_format={"type": "json_object"},
        direct=True,
    )

    # Step 6 & 7: Handle degraded call or JSON parsing errors
    if result.degraded:
        judge_results = [
            {
                "sentence": sentence,
                "marker": marker,
                "status": "unverified",
                "reason": "Citation judge call degraded (proxy unavailable)."
            }
            for sentence, marker, _, _ in judge_batch
        ]
    else:
        judge_results = []
        try:
            parsed = json.loads(result.content)
            results_list = parsed.get("results", [])

            # Map each judge result back to the corresponding (sentence, marker) pair
            # by marker string
            judge_dict = {item.get("marker"): item for item in results_list}

            for sentence, marker, _, _ in judge_batch:
                judge_item = judge_dict.get(marker, {})
                if not judge_item:
                    # Shouldn't happen, but default to unverified
                    judge_results.append({
                        "sentence": sentence,
                        "marker": marker,
                        "status": "unverified",
                        "reason": "Judge response did not include this marker."
                    })
                else:
                    judge_results.append({
                        "sentence": sentence,
                        "marker": marker,
                        "status": judge_item.get("status", "unverified"),
                        "reason": judge_item.get("reason", "No reason provided.")
                    })
        except (json.JSONDecodeError, TypeError):
            # JSON parsing failed -> all pairs in this batch get unverified
            judge_results = [
                {
                    "sentence": sentence,
                    "marker": marker,
                    "status": "unverified",
                    "reason": "Citation judge call returned invalid JSON."
                }
                for sentence, marker, _, _ in judge_batch
            ]

    # Step 9: Combine all results in the order they appeared in raw_text
    all_results = uncited_results + invalid_marker_results + judge_results
    return all_results


def check_differential(
    client: ParitokLLMClient,
    papers: list[dict],
    differential_candidates: list[dict],
    *,
    on_stage: Callable[[str, dict], None] | None = None,
) -> list[dict]:
    """Verify each differential candidate's marker against its cited abstract.

    differential_candidates: list of {"condition_name": str, "marker": str}.
    Returns a list of {"condition_name": str, "marker": str, "pmid": str} for
    candidates the judge confirms the abstract supports as a plausible alternate.
    Unsupported, invalid-marker, degraded, or malformed-response candidates are dropped.
    """
    if not papers or not differential_candidates:
        return []

    valid_batch = []  # (condition_name, marker, abstract, pmid)
    for candidate in differential_candidates:
        condition_name = candidate.get("condition_name")
        marker = candidate.get("marker") or ""
        match = re.match(r"^\[(\d+)\]$", marker.strip())
        if not match:
            continue
        marker_num = int(match.group(1))
        if not (1 <= marker_num <= len(papers)):
            continue
        paper = papers[marker_num - 1]
        valid_batch.append((condition_name, marker, paper["abstract"], paper["pmid"]))

    if not valid_batch:
        return []

    batch_claims = [
        {"condition_name": condition_name, "marker": marker, "abstract": abstract}
        for condition_name, marker, abstract, _ in valid_batch
    ]

    user_prompt = f"""Evaluate each candidate differential diagnosis and its cited abstract below:

{json.dumps(batch_claims, indent=2)}

For each, determine if the abstract genuinely supports this condition as a plausible alternate diagnosis. Return ONLY valid JSON."""

    messages = [
        {"role": "system", "content": DIFFERENTIAL_CHECK_SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]

    if on_stage:
        on_stage("citation_check", {})
    result = client.chat(messages, response_format={"type": "json_object"}, direct=True)

    if result.degraded:
        return []

    try:
        parsed = json.loads(result.content)
        results_list = parsed.get("results", [])
        judge_dict = {
            (item.get("condition_name"), item.get("marker")): item
            for item in results_list
        }
    except (json.JSONDecodeError, TypeError, AttributeError):
        return []

    verified = []
    for condition_name, marker, _, pmid in valid_batch:
        judge_item = judge_dict.get((condition_name, marker))
        if judge_item and judge_item.get("status") == "supported":
            verified.append({"condition_name": condition_name, "marker": marker, "pmid": pmid})

    return verified
