"""Self-correcting search loop (plan.md Step 4.2): HyDE-expand, retrieve,
relevance-check, and on failure refine the query using Self-Query
Refinement, carrying prior-iteration reasoning forward (not isolated calls)
so the loop visibly catches and fixes a bad retrieval, not just succeeds
silently.
"""
from __future__ import annotations

from collections.abc import Callable

from backend.app.loop.hyde import build_hyde_prompt
from backend.app.loop.relevance_check import run_relevance_check_batch
from backend.app.loop.trace import LoopTraceEntry
from backend.contracts.models import ScoredPaper
from backend.contracts.ports import LLMPort, RetrievalPort


def _paper_dict(sp: ScoredPaper) -> dict:
    return {
        "pmid": sp.paper.pmid,
        "title": sp.paper.title,
        "abstract": sp.paper.abstract,
        "journal": sp.paper.journal,
        "year": sp.paper.year,
        "condition": sp.paper.condition,
        "is_rare": sp.paper.is_rare,
        "url": sp.paper.url,
        "score": sp.score,
    }


def run_search_loop(
    client: LLMPort,
    retriever: RetrievalPort,
    query: str,
    *,
    request_id: str,
    session_id: str,
    user_id: str,
    max_iterations: int = 2,
    top_k: int = 5,
    on_stage: Callable[[str, dict], None] | None = None,
) -> tuple[list[dict], list[LoopTraceEntry]]:
    trace: list[LoopTraceEntry] = []
    current_query = query
    prior_reasoning = ""

    for iteration in range(1, max_iterations + 1):
        hyde_messages = build_hyde_prompt(current_query)
        if prior_reasoning:
            hyde_messages[-1]["content"] += f"\nPrior iteration reasoning: {prior_reasoning}"
        if on_stage:
            on_stage("hyde_expand", {"iteration": iteration})
        hyde_result = client.chat(
            hyde_messages,
            call_site="hyde",
            request_id=request_id,
            session_id=session_id,
            user_id=user_id,
        )

        # Run retrieval with both raw query and HyDE-expanded text (weighted merge)
        retrieved = retriever.search(current_query, secondary_query=hyde_result.content, top_k=top_k)
        papers = [_paper_dict(sp) for sp in retrieved]
        if on_stage:
            on_stage("retrieval", {"iteration": iteration})

        # Batch relevance check: evaluate all top-k papers at once
        if papers:
            batch_check = run_relevance_check_batch(
                client,
                current_query,
                papers,
                request_id=request_id,
                session_id=session_id,
                user_id=user_id,
            )
            relevant_results = batch_check.get("results", {})

            # Filter to only relevant papers
            relevant_papers = [p for p in papers if relevant_results.get(p["pmid"], {}).get("relevant", False)]
            relevant_count = len(relevant_papers)
            total_count = len(papers)

            # Compute overall confidence (max of relevant papers' confidences)
            if relevant_papers:
                overall_confidence = max(relevant_results.get(p["pmid"], {}).get("confidence", 0.0) for p in relevant_papers)
            else:
                overall_confidence = 0.0
        else:
            relevant_papers = []
            relevant_count = 0
            total_count = 0
            overall_confidence = 0.0

        if on_stage:
            on_stage("relevance_check", {"iteration": iteration})

        # Determine pass/fail: need at least 2 relevant papers
        iteration_passed = relevant_count >= 2

        trace.append(LoopTraceEntry(
            iteration=iteration,
            retrieved_pmids=[p["pmid"] for p in papers],
            relevant=iteration_passed,
            confidence=overall_confidence,
            note=(f"iteration {iteration} retrieved {total_count} papers -> "
                  f"{relevant_count}/{total_count} passed relevance check -> "
                  f"{'passed' if iteration_passed else 'flagged low confidence'}"),
            relevant_count=relevant_count,
            total_count=total_count,
        ))

        if iteration_passed or iteration == max_iterations:
            # relevant_papers is already filtered to only relevance-check-passed papers, so it's
            # safe to return as-is even on a final iteration below the 2-paper floor - if it has
            # 1+ paper, the caller uses low_confidence=True; if it's empty, the caller falls back
            # to no_match.
            return relevant_papers, trace

        prior_reasoning = f"iteration {iteration} flagged: {relevant_count}/{total_count} papers passed relevance"
        refine_prompt = [
            {"role": "system", "content": "Refine the search query given the prior iteration's low-confidence result."},
            {"role": "user", "content": f"Original query: {current_query}\nPrior reasoning: {prior_reasoning}"},
        ]
        if on_stage:
            on_stage("refine_query", {"iteration": iteration})
        refined = client.chat(
            refine_prompt,
            call_site="refine",
            request_id=request_id,
            session_id=session_id,
            user_id=user_id,
        )
        current_query = refined.content or current_query
