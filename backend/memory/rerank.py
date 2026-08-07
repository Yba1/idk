"""FROZEN filename at tag contracts-v1. Body owned by Card 2A (EverMind memory).

Memory-conditioned re-rank applied on top of RetrievalPort.search results
(sets ScoredPaper.memory_multiplier), per
plan-v2/00-SHARED-CONTRACTS.md section 0/2.2.
"""
from __future__ import annotations


class MemoryReranker:
    def __init__(self, *args, **kwargs) -> None:
        raise NotImplementedError("MemoryReranker: implemented by Card 2A (EverMind memory)")
