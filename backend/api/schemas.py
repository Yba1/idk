from __future__ import annotations

from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    query: str = Field(min_length=1, max_length=500)


class TraceEntryOut(BaseModel):
    iteration: int
    retrieved_pmids: list[str]
    relevant: bool
    confidence: float
    note: str
    relevant_count: int = 0
    total_count: int = 0


class CitationOut(BaseModel):
    marker: str
    pmid: str
    title: str
    condition: str


class SuggestedConditionOut(BaseModel):
    name: str
    paper_count: int


class QueryResponse(BaseModel):
    summary_text: str
    citations: list[CitationOut]
    trace: list[TraceEntryOut]
    low_confidence: bool
    degraded: bool
    no_match: bool = False
    too_generic: bool = False
    example_query: str | None = None
    suggested_conditions: list[SuggestedConditionOut] = []
    flagged_claims: list[dict] = []
    case_context: CaseContextOut | None = None
    differential: list[DifferentialItemOut] = []


class ContrastPaperOut(BaseModel):
    pmid: str
    title: str
    condition: str
    rarity: str


class DemoContrastResponse(BaseModel):
    query: str
    naive: list[ContrastPaperOut]
    weighted: list[ContrastPaperOut]
    rare_case_pmid: str


class ConditionOut(BaseModel):
    name: str
    rarity: str
    region_literature: str
    atlas_label: str
    overlaps_with: list[str]


class CaseContextOut(BaseModel):
    condition_name: str
    rarity: str
    region_literature: str
    atlas_label: str
    corpus_paper_count: int
    imaging_findings: str | None = None
    teaching_point: str | None = None


class DifferentialItemOut(BaseModel):
    condition_name: str
    marker: str
    pmid: str
