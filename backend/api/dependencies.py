"""Process-lifetime singletons for the API layer. Building the retriever
constructs a SentenceTransformer and embeds the full corpus, so it must be
cached, not rebuilt per request - a live demo can't pay that cost on every
query.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from backend.app.llm_client import ParitokLLMClient
from backend.app.retrieval.demo_fixture import run_demo_contrast
from backend.app.retrieval.hybrid import HybridRetriever

CORPUS_PATH = Path(__file__).resolve().parent.parent / "data" / "corpus.json"


@lru_cache(maxsize=1)
def get_llm_client() -> ParitokLLMClient:
    return ParitokLLMClient()


@lru_cache(maxsize=1)
def get_retriever() -> HybridRetriever:
    corpus = json.loads(CORPUS_PATH.read_text())
    return HybridRetriever(corpus)


@lru_cache(maxsize=1)
def get_demo_contrast() -> dict:
    return run_demo_contrast()
