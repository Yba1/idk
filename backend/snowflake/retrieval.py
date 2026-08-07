"""FROZEN filename at tag contracts-v1. Body owned by Card 1 (Snowflake platform).

Must implement backend.contracts.ports.RetrievalPort against Cortex Search
Service, per plan-v2/00-SHARED-CONTRACTS.md section 2.2.
"""
from __future__ import annotations


class CortexSearchRetriever:
    def __init__(self, *args, **kwargs) -> None:
        raise NotImplementedError("CortexSearchRetriever: implemented by Card 1 (Snowflake platform)")
