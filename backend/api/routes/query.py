from __future__ import annotations

import json
import logging
import queue
import re
import threading
from collections.abc import Callable
from dataclasses import asdict

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from backend.api.dependencies import get_llm_client, get_retriever
from backend.api.limiter import limiter
from backend.api.schemas import (
    CaseContextOut,
    DifferentialItemOut,
    QueryRequest,
    QueryResponse,
    SuggestedConditionOut,
)
from backend.app.corpus.conditions import CONDITIONS
from backend.app.llm_client import ParitokLLMClient
from backend.app.loop.refine import run_search_loop
from backend.app.retrieval.condition_match import NO_MATCH_THRESHOLD
from backend.app.retrieval.hybrid import HybridRetriever
from backend.app.retrieval.query_specificity import build_example_query, is_query_too_generic
from backend.app.summary.generate import generate_sourced_summary
from backend.app.verify.citation_check import check_citations, check_differential

logger = logging.getLogger(__name__)
router = APIRouter()

SPARSITY_FLOOR = 10


def _is_self_reference(candidate_name: str, best_condition: str) -> bool:
    norm = lambda s: re.sub(r"[^a-z0-9 ]", "", s.lower()).strip()
    a, b = norm(candidate_name), norm(best_condition)
    if a == b:
        return True
    shorter, longer = (a, b) if len(a) <= len(b) else (b, a)
    return bool(shorter) and shorter in longer and len(shorter) / len(longer) >= 0.5


def _run_query_pipeline(
    payload: QueryRequest,
    client: ParitokLLMClient,
    retriever: HybridRetriever,
    on_stage: Callable[[str, dict], None] | None = None,
) -> QueryResponse:
    papers, trace = run_search_loop(client, retriever, payload.query, on_stage=on_stage)
    low_confidence = bool(trace) and not trace[-1].relevant
    too_generic = is_query_too_generic(payload.query)

    # Check if no papers survived the relevance filter
    if not papers:
        # Out-of-scope query: get suggested conditions
        closest = retriever.get_closest_conditions(payload.query, top_n=3)
        suggested_conditions = []
        for condition_name, similarity, paper_count in closest:
            if similarity >= NO_MATCH_THRESHOLD:
                suggested_conditions.append(
                    SuggestedConditionOut(name=condition_name, paper_count=paper_count)
                )

        example_query = None
        if too_generic and suggested_conditions:
            nearest = next(
                (c for c in CONDITIONS if c.name == suggested_conditions[0].name), None
            )
            if nearest is not None:
                example_query = build_example_query(nearest.region_literature)

        return QueryResponse(
            summary_text="",
            citations=[],
            trace=[asdict(t) for t in trace],
            low_confidence=False,
            degraded=False,
            no_match=True,
            too_generic=too_generic,
            example_query=example_query,
            suggested_conditions=suggested_conditions,
            flagged_claims=[],
        )

    top_papers = papers[:5] if papers else []

    # Check if best-matching condition has sparse coverage.
    # corpus_paper_count is computed against the FULL corpus (retriever.papers),
    # not the relevance-filtered/capped `papers` list, which can never exceed 5
    # items (run_search_loop calls retriever.search(..., top_k=5)).
    if top_papers:
        best_condition = top_papers[0].get("condition", "")
        corpus_paper_count = sum(1 for p in retriever.papers if p.get("condition") == best_condition)
    else:
        best_condition = ""
        corpus_paper_count = 0

    sparse_coverage = corpus_paper_count < SPARSITY_FLOOR

    # Look up static condition facts before the summary call (data available
    # regardless of whether the summary call itself later degrades).
    condition_lookup = next((c for c in CONDITIONS if c.name == best_condition), None)

    summary = generate_sourced_summary(
        client, payload.query, top_papers, low_confidence=low_confidence, sparse_coverage=sparse_coverage, on_stage=on_stage,
    )

    # generate_sourced_summary builds citations in the same order as top_papers
    # (enumerate(papers) in backend/app/summary/generate.py), so citation i's
    # condition is top_papers[i]["condition"] - joined by position, not a shared key.
    citations = [
        {**citation, "condition": top_papers[i]["condition"]}
        for i, citation in enumerate(summary.citations)
    ]

    # Verify each citation against its source paper's abstract, and verify
    # any model-proposed differential candidates, only when the summary call
    # actually produced JSON to parse.
    flagged_claims = []
    differential: list[DifferentialItemOut] = []
    if not summary.degraded:
        candidates = [
            c for c in summary.differential_candidates
            if not _is_self_reference(c["condition_name"], best_condition)
        ]

        # check_citations and check_differential are independent LLM calls (both
        # read-only against the already-generated summary/papers), so run them
        # concurrently instead of back-to-back - halves this stage's latency.
        results: dict[str, list] = {}

        def _run_citations() -> None:
            results["flagged_claims"] = check_citations(
                client, payload.query, summary.raw_text, top_papers, on_stage=on_stage
            )

        def _run_differential() -> None:
            results["differential"] = check_differential(client, top_papers, candidates, on_stage=on_stage)

        threads = [threading.Thread(target=_run_citations)]
        if candidates:
            threads.append(threading.Thread(target=_run_differential))
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        flagged_claims = results.get("flagged_claims", [])
        if candidates:
            differential = [DifferentialItemOut(**v) for v in results.get("differential", [])]

    # case_context is built from the Condition lookup, but discarded whenever
    # the summary call degraded - the invariant "case_context is None when
    # degraded" is a deliberate discard here, not a missing code path.
    case_context = None
    if condition_lookup is not None and not summary.degraded:
        case_context = CaseContextOut(
            condition_name=condition_lookup.name,
            rarity=condition_lookup.rarity,
            region_literature=condition_lookup.region_literature,
            atlas_label=condition_lookup.atlas_label,
            corpus_paper_count=corpus_paper_count,
            imaging_findings=summary.imaging_findings,
            teaching_point=summary.teaching_point,
        )

    example_query = None
    if too_generic and condition_lookup is not None:
        example_query = build_example_query(condition_lookup.region_literature)

    return QueryResponse(
        summary_text=summary.text,
        citations=citations,
        trace=[asdict(t) for t in trace],
        low_confidence=low_confidence,
        degraded=summary.degraded,
        no_match=False,
        too_generic=too_generic,
        example_query=example_query,
        suggested_conditions=[],
        flagged_claims=flagged_claims,
        case_context=case_context,
        differential=differential,
    )


@router.post("/query", response_model=QueryResponse)
@limiter.limit("10/minute")
def query(
    request: Request,
    payload: QueryRequest,
    client: ParitokLLMClient = Depends(get_llm_client),
    retriever: HybridRetriever = Depends(get_retriever),
) -> QueryResponse:
    return _run_query_pipeline(payload, client, retriever)


@router.post("/query/stream")
@limiter.limit("10/minute")
def query_stream(
    request: Request,
    payload: QueryRequest,
    client: ParitokLLMClient = Depends(get_llm_client),
    retriever: HybridRetriever = Depends(get_retriever),
) -> StreamingResponse:
    event_queue: queue.Queue = queue.Queue()

    def on_stage(stage: str, detail: dict) -> None:
        event_queue.put({"type": "stage", "stage": stage, **detail})

    def worker() -> None:
        try:
            result = _run_query_pipeline(payload, client, retriever, on_stage=on_stage)
            event_queue.put({"type": "done", "result": result.model_dump()})
        except Exception:
            logger.exception("Unhandled error in /query/stream pipeline")
            event_queue.put({"type": "error", "message": "Internal error while processing query."})
        finally:
            event_queue.put(None)

    threading.Thread(target=worker, daemon=True).start()

    def event_generator():
        while True:
            item = event_queue.get()
            if item is None:
                break
            yield f"data: {json.dumps(item)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
