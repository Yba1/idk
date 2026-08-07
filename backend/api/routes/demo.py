"""The fixed demo contrast (naive vs rarity-weighted retrieval) built
directly against RetrievalPort, so it works identically under every profile
and never depends on backend/app/retrieval/demo_fixture.py (Card 1's file,
which imports the deleted v1 HybridRetriever and isn't ours to fix).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from backend.api.dependencies import get_services_dep
from backend.api.schemas import ContrastPaperOut, DemoContrastResponse
from backend.contracts.models import ScoredPaper
from backend.contracts.registry import Services

router = APIRouter()

DEMO_QUERY = "localized hypermetabolic uptake pattern on brain imaging"


def _to_contrast_papers(scored: list[ScoredPaper]) -> list[ContrastPaperOut]:
    return [
        ContrastPaperOut(
            pmid=sp.paper.pmid,
            title=sp.paper.title,
            condition=sp.paper.condition,
            rarity="rare" if sp.paper.is_rare else "common",
        )
        for sp in scored
    ]


@router.get("/demo-contrast", response_model=DemoContrastResponse)
def demo_contrast(services: Services = Depends(get_services_dep)) -> DemoContrastResponse:
    naive = services.retrieval.search(DEMO_QUERY, top_k=5, apply_rarity=False)
    weighted = services.retrieval.search(DEMO_QUERY, top_k=5, apply_rarity=True)
    rare = next((sp for sp in weighted if sp.paper.is_rare), None)

    return DemoContrastResponse(
        query=DEMO_QUERY,
        naive=_to_contrast_papers(naive),
        weighted=_to_contrast_papers(weighted),
        rare_case_pmid=rare.paper.pmid if rare else "",
    )
