"""FROZEN filename at tag contracts-v1. Body owned by Card 1 (Snowflake platform).

Must implement backend.contracts.ports.LedgerPort, writing to Snowflake's
TOKEN_LEDGER table, per plan-v2/00-SHARED-CONTRACTS.md section 0/2.2.
"""
from __future__ import annotations


class SnowflakeLedger:
    def __init__(self, *args, **kwargs) -> None:
        raise NotImplementedError("SnowflakeLedger: implemented by Card 1 (Snowflake platform)")
