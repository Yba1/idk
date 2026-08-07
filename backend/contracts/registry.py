"""FROZEN at tag contracts-v1."""
from __future__ import annotations
import functools, importlib, os
from dataclasses import dataclass
import yaml
from backend.contracts.ports import LLMPort, LedgerPort, MemoryPort, RetrievalPort

_CONFIG = os.environ.get("NEULIT_SERVICES_CONFIG", "config/services.yaml")


@dataclass
class Services:
    retrieval: RetrievalPort
    llm: LLMPort
    memory: MemoryPort
    ledger: LedgerPort


def _load(path: str):
    module_path, _, cls_name = path.rpartition(".")
    return getattr(importlib.import_module(module_path), cls_name)()


@functools.lru_cache(maxsize=1)
def get_services() -> Services:
    profile = os.environ.get("NEULIT_PROFILE", "fake")
    with open(_CONFIG) as fh:
        cfg = yaml.safe_load(fh)[profile]
    return Services(
        retrieval=_load(cfg["retrieval"]),
        llm=_load(cfg["llm"]),
        memory=_load(cfg["memory"]),
        ledger=_load(cfg["ledger"]),
    )
