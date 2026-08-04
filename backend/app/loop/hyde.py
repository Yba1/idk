"""HyDE (Hypothetical Document Embeddings) query expansion: ask the model to
write a plausible case report for the query, then retrieve against that
hypothetical text instead of the short raw query, since case-report language
matches literature far better than a short symptom description does.
"""
from __future__ import annotations

from backend.app.llm_client import ChatResult, ParitokLLMClient


def build_hyde_prompt(query: str) -> list[dict]:
    return [
        {"role": "system", "content": (
            "You write a short, plausible medical case report abstract (3-5 sentences) "
            "describing a PET/neuroimaging finding matching the user's query. This is used "
            "purely to improve literature retrieval matching, not as medical advice."
        )},
        {"role": "user", "content": f"Query: {query}"},
    ]


def run_hyde(client: ParitokLLMClient, query: str, *, direct: bool = False) -> ChatResult:
    return client.chat(build_hyde_prompt(query), direct=direct)
