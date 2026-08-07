from __future__ import annotations

import json
import logging
import queue
import threading

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from backend.api.limiter import limiter
from backend.api.schemas import (
    BrainRegionOut,
    CallSiteCostOut,
    CitationOut,
    CostOut,
    MemoryOut,
    PaperOut,
    QueryRequest,
    QueryResponse,
    ScoredPaperOut,
    TraceRoundOut,
)
from backend.app.pipeline import QueryResult, run_query

logger = logging.getLogger(__name__)
router = APIRouter()


def _to_response(result: QueryResult) -> QueryResponse:
    return QueryResponse(
        request_id=result.request_id,
        summary_markdown=result.summary_markdown,
        citations=[
            CitationOut(index=c.index, pmid=c.pmid, supported=c.supported, note=c.note)
            for c in result.citations
        ],
        papers=[
            ScoredPaperOut(
                paper=PaperOut(
                    pmid=sp.paper.pmid,
                    title=sp.paper.title,
                    abstract=sp.paper.abstract,
                    journal=sp.paper.journal,
                    year=sp.paper.year,
                    condition=sp.paper.condition,
                    is_rare=sp.paper.is_rare,
                    url=sp.paper.url,
                ),
                score=sp.score,
                lexical_score=sp.lexical_score,
                semantic_score=sp.semantic_score,
                rarity_multiplier=sp.rarity_multiplier,
                memory_multiplier=sp.memory_multiplier,
            )
            for sp in result.papers
        ],
        trace=[
            TraceRoundOut(
                iteration=t.iteration,
                retrieved_pmids=t.retrieved_pmids,
                relevant=t.relevant,
                confidence=t.confidence,
                note=t.note,
                memory_applied=t.memory_applied,
                seen_filtered=t.seen_filtered,
            )
            for t in result.trace
        ],
        region=(
            BrainRegionOut(
                name=result.region.name,
                atlas_label=result.region.atlas_label,
                region_literature=result.region.region_literature,
            )
            if result.region is not None
            else None
        ),
        memory=MemoryOut(
            applied=result.memory.applied,
            seen_filtered=result.memory.seen_filtered,
            profile_used=result.memory.profile_used,
            distilled_context=result.memory.distilled_context,
        ),
        cost=CostOut(
            total_tokens=result.cost.total_tokens,
            cost_usd=result.cost.cost_usd,
            by_call_site={
                site: CallSiteCostOut(tokens=c.tokens, cost_usd=c.cost_usd)
                for site, c in result.cost.by_call_site.items()
            },
        ),
    )


@router.post("/query", response_model=QueryResponse)
@limiter.limit("10/minute")
def query(request: Request, payload: QueryRequest) -> QueryResponse:
    result = run_query(payload.query, payload.user_id, payload.session_id, payload.personalize)
    return _to_response(result)


@router.post("/query/stream")
@limiter.limit("10/minute")
def query_stream(request: Request, payload: QueryRequest) -> StreamingResponse:
    """Runs the same pipeline as POST /query but over SSE, emitting `stage`
    events as the search loop progresses (hyde_expand, retrieval,
    relevance_check, refine_query, summarize, citation_check - the same
    stage names v1 used) followed by one `done` event with the full result.
    The frozen HTTP contract in plan-v2/00-SHARED-CONTRACTS.md section 4
    doesn't define this route's event shape, so it's ours to choose; matching
    v1's stage names is what frontend/src/components/progress-timeline.tsx
    already expects.
    """
    event_queue: queue.Queue = queue.Queue()

    def on_stage(stage: str, detail: dict) -> None:
        event_queue.put({"type": "stage", "stage": stage, **detail})

    def worker() -> None:
        try:
            result = _to_response(run_query(
                payload.query, payload.user_id, payload.session_id, payload.personalize,
                on_stage=on_stage,
            ))
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
