"""Measurement gate, Candidate A (plan.md Step 2.1): the search loop's calls
- HyDE expansion, relevance self-check, refinement - run for real across two
simulated iterations so prior-iteration reasoning is carried forward (not
three isolated short calls), matching the "historical context inflation"
framing in plan/plan.md's Positioning section. Run once through the proxy,
once direct to Groq, and compare summed prompt_tokens.
"""
from __future__ import annotations

import json
from pathlib import Path

from backend.app.llm_client import ParitokLLMClient
from backend.app.loop.hyde import build_hyde_prompt
from backend.app.loop.relevance_check import build_relevance_check_prompt

CORPUS_PATH = Path(__file__).resolve().parent.parent / "data" / "corpus.json"
SAMPLE_QUERY = "hypometabolism in a rare autoimmune encephalitis with insular involvement"


def _sample_abstract() -> str:
    corpus = json.loads(CORPUS_PATH.read_text())
    match = next((p for p in corpus if p["condition"] == "Anti-NMDA receptor encephalitis"), corpus[0])
    return match["abstract"]


def _run_loop_calls(client: ParitokLLMClient, *, direct: bool) -> int:
    abstract = _sample_abstract()
    total = 0

    hyde_1 = client.chat(build_hyde_prompt(SAMPLE_QUERY), direct=direct)
    total += hyde_1.prompt_tokens

    relcheck_1 = client.chat(
        build_relevance_check_prompt(SAMPLE_QUERY, abstract),
        response_format={"type": "json_object"}, direct=direct)
    total += relcheck_1.prompt_tokens

    refine_prompt = [
        {"role": "system", "content": "Refine the search query given the prior iteration's reasoning."},
        {"role": "user", "content": (
            f"Original query: {SAMPLE_QUERY}\n"
            f"Iteration 1 hypothetical case: {hyde_1.content}\n"
            f"Iteration 1 relevance check: {relcheck_1.content}\n"
            "Produce a refined, more specific query."
        )},
    ]
    refine = client.chat(refine_prompt, direct=direct)
    total += refine.prompt_tokens

    hyde_2_prompt = build_hyde_prompt(refine.content)
    hyde_2_prompt[-1]["content"] += f"\nPrior iteration reasoning: {relcheck_1.content}"
    hyde_2 = client.chat(hyde_2_prompt, direct=direct)
    total += hyde_2.prompt_tokens

    relcheck_2 = client.chat(
        build_relevance_check_prompt(refine.content, abstract),
        response_format={"type": "json_object"}, direct=direct)
    total += relcheck_2.prompt_tokens

    return total


def run_candidate_a(client: ParitokLLMClient) -> dict:
    proxied = _run_loop_calls(client, direct=False)
    direct = _run_loop_calls(client, direct=True)
    reduction_pct = 0.0 if direct == 0 else (direct - proxied) / direct * 100
    return {
        "proxied_prompt_tokens": proxied,
        "direct_prompt_tokens": direct,
        "reduction_pct": round(reduction_pct, 2),
    }
