from __future__ import annotations

from dataclasses import dataclass


@dataclass
class LoopTraceEntry:
    iteration: int
    retrieved_pmids: list[str]
    relevant: bool
    confidence: float
    note: str
    memory_applied: bool = False
    seen_filtered: int = 0
