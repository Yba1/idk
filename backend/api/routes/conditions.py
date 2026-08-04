from __future__ import annotations

from fastapi import APIRouter

from backend.api.schemas import ConditionOut
from backend.app.corpus.conditions import CONDITIONS

router = APIRouter()


@router.get("/conditions", response_model=list[ConditionOut])
def conditions() -> list[ConditionOut]:
    return [
        ConditionOut(
            name=c.name,
            rarity=c.rarity,
            region_literature=c.region_literature,
            atlas_label=c.atlas_label,
            overlaps_with=c.overlaps_with,
        )
        for c in CONDITIONS
    ]
