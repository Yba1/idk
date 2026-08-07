"""FROZEN filename at tag contracts-v1. Body owned by Card 2A (EverMind memory).

Must implement backend.contracts.ports.MemoryPort against the EverOS SDK,
per plan-v2/00-SHARED-CONTRACTS.md section 2.2.
"""
from __future__ import annotations


class EverOSMemory:
    def __init__(self, *args, **kwargs) -> None:
        raise NotImplementedError("EverOSMemory: implemented by Card 2A (EverMind memory)")
