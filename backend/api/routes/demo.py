from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, Depends

from backend.api.dependencies import get_demo_contrast
from backend.api.schemas import ContrastPaperOut, DemoContrastResponse
from backend.app.retrieval.demo_fixture import DEMO_QUERY

router = APIRouter()
CORPUS_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "corpus.json"


def _papers_by_pmid() -> dict[str, dict]:
    corpus = json.loads(CORPUS_PATH.read_text())
    return {p["pmid"]: p for p in corpus}


@router.get("/demo-contrast", response_model=DemoContrastResponse)
def demo_contrast(result: dict = Depends(get_demo_contrast)) -> DemoContrastResponse:
    lookup = _papers_by_pmid()

    def _to_out(pmids: list[str]) -> list[ContrastPaperOut]:
        return [
            ContrastPaperOut(
                pmid=pmid,
                title=lookup[pmid]["title"],
                condition=lookup[pmid]["condition"],
                rarity=lookup[pmid]["rarity"],
            )
            for pmid in pmids
        ]

    return DemoContrastResponse(
        query=DEMO_QUERY,
        naive=_to_out(result["naive_top5"]),
        weighted=_to_out(result["weighted_top5"]),
        rare_case_pmid=result["rare_case_pmid"],
    )
