from dataclasses import dataclass


@dataclass
class LoopTraceEntry:
    iteration: int
    retrieved_pmids: list[str]
    relevant: bool
    confidence: float
    note: str
    relevant_count: int = 0
    total_count: int = 0
