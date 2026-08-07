"""Process-lifetime singletons for the API layer. Building the retriever
constructs a SentenceTransformer and embeds the full corpus, so it must be
cached, not rebuilt per request - a live demo can't pay that cost on every
query.
"""
from __future__ import annotations

from functools import lru_cache

from backend.app.retrieval.demo_fixture import run_demo_contrast
from backend.contracts.ports import LLMPort, RetrievalPort
from backend.contracts.registry import get_services


def get_llm_client() -> LLMPort:
    return get_services().llm


def get_retriever() -> RetrievalPort:
    return get_services().retrieval


@lru_cache(maxsize=1)
def get_demo_contrast() -> dict:
    return run_demo_contrast()
