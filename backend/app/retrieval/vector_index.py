from __future__ import annotations

from sentence_transformers import SentenceTransformer

MODEL_NAME = "all-MiniLM-L6-v2"


class VectorIndex:
    def __init__(self, papers: list[dict]) -> None:
        self.papers = papers
        self._model = SentenceTransformer(MODEL_NAME)
        texts = [f"{p['title']} {p['abstract']}" for p in papers]
        self._embeddings = self._model.encode(texts, normalize_embeddings=True)

    def search(self, query: str, top_k: int = 10) -> list[tuple[dict, float]]:
        if not self.papers:
            return []
        query_vec = self._model.encode([query], normalize_embeddings=True)[0]
        scores = self._embeddings @ query_vec
        ranked = sorted(zip(self.papers, scores), key=lambda pair: pair[1], reverse=True)
        return [(p, float(s)) for p, s in ranked[:top_k]]
