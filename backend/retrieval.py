from typing import Dict, List

import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity


class SemanticRetriever:
    """Small in-memory semantic retriever using sentence-transformers + cosine similarity."""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2") -> None:
        self.model = SentenceTransformer(model_name)
        self.chunks: List[Dict[str, object]] = []
        self.embeddings: np.ndarray | None = None

    def build_index(self, chunks: List[Dict[str, object]]) -> None:
        self.chunks = chunks
        if not chunks:
            self.embeddings = None
            return

        texts = [str(chunk["text"]) for chunk in chunks]
        self.embeddings = self.model.encode(
            texts,
            convert_to_numpy=True,
            normalize_embeddings=True,
        )

    def search(self, query: str, top_k: int = 4) -> List[Dict[str, object]]:
        if not query.strip() or not self.chunks or self.embeddings is None:
            return []

        query_embedding = self.model.encode(
            [query],
            convert_to_numpy=True,
            normalize_embeddings=True,
        )
        similarities = cosine_similarity(query_embedding, self.embeddings)[0]

        top_k = max(1, min(top_k, len(self.chunks)))
        ranked_indices = np.argsort(similarities)[::-1][:top_k]

        results: List[Dict[str, object]] = []
        for idx in ranked_indices:
            chunk = self.chunks[int(idx)]
            results.append(
                {
                    "chunk_id": chunk["chunk_id"],
                    "page": chunk["page"],
                    "text": chunk["text"],
                    "score": float(similarities[int(idx)]),
                }
            )
        return results
