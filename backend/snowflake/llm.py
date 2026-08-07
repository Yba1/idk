"""FROZEN filename at tag contracts-v1. Body owned by Card 1 (Snowflake platform).

Must implement backend.contracts.ports.LLMPort against Cortex COMPLETE, and
must call LedgerPort.record exactly once per chat() call (including on the
degraded path), per plan-v2/00-SHARED-CONTRACTS.md section 2.2.
"""
from __future__ import annotations


class CortexLLMClient:
    def __init__(self, *args, **kwargs) -> None:
        raise NotImplementedError("CortexLLMClient: implemented by Card 1 (Snowflake platform)")
