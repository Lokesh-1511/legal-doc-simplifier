"""
Semantic-first retrieval with lightweight keyword reranking.

This module keeps retrieval simple and realistic:
1. Embed the document chunks once
2. Embed the user query
3. Compute cosine similarity for top candidates
4. Apply a tiny keyword-based rerank
5. Let the LLM do the final evidence selection when needed

Why this scales better than rule-based expansion:
- No manual synonym dictionary to maintain
- Embeddings handle meaning directly
- Small rerank step adds a useful lexical signal without becoming a rules engine
"""

from __future__ import annotations

from typing import Dict, List
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

from .embeddings_hf import get_hf_embeddings
from .retrieval_helpers import extract_keywords, normalize_query


class SemanticRetriever:
    def __init__(self) -> None:
        self.chunks: List[Dict[str, object]] = []
        self.embeddings: np.ndarray | None = None

    def build_index(self, chunks: List[Dict[str, object]]) -> None:
        self.chunks = chunks
        if not chunks:
            self.embeddings = None
            print("⚠️ No chunks to index")
            return

        texts = [str(chunk["text"]) for chunk in chunks]
        print(f"📊 Embedding {len(chunks)} chunks for retrieval index...")
        try:
            self.embeddings = get_hf_embeddings(texts)
            embedding_dim = self.embeddings.shape[1] if self.embeddings.ndim > 1 else 1
            print(f"✅ Retrieval index ready: {len(chunks)} chunks, {embedding_dim}-dim embeddings")
        except Exception as error:
            print(f"❌ Embedding error: {error}")
            self.embeddings = None

    def search(self, query: str, top_k: int = 5, min_similarity: float = 0.25) -> List[Dict[str, object]]:
        """
        Retrieve the most relevant chunks for a question.

        The threshold is intentionally soft: if the document is weakly related, we still
        return the best available chunks instead of forcing an empty result.
        """
        if not query.strip() or not self.chunks or self.embeddings is None:
            print("⚠️ No indexed chunks available for search")
            return []

        normalized_query = normalize_query(query)
        print(f"\n🔍 Query: '{query}' → '{normalized_query}'")

        try:
            query_embedding = get_hf_embeddings([normalized_query])
        except Exception as error:
            print(f"❌ Query embedding error: {error}")
            return []

        similarities = cosine_similarity(query_embedding, self.embeddings)[0]
        threshold_count = int(np.sum(similarities >= min_similarity))
        print(
            f"📊 Similarity scores: min={similarities.min():.3f}, max={similarities.max():.3f}, "
            f"avg={similarities.mean():.3f}, above_threshold={threshold_count}"
        )

        candidate_indices = np.where(similarities >= min_similarity)[0]
        if len(candidate_indices) == 0:
            candidate_indices = np.argsort(similarities)[::-1][:top_k]
            print(f"⚠️ No chunks above threshold; using best {len(candidate_indices)} fallback matches")
        else:
            candidate_indices = candidate_indices[
                np.argsort(similarities[candidate_indices])[::-1]
            ][:top_k]

        keywords = extract_keywords(normalized_query)
        results: List[Dict[str, object]] = []
        for index in candidate_indices:
            chunk = self.chunks[int(index)]
            semantic_score = float(similarities[int(index)])
            text_lower = str(chunk["text"]).lower()
            keyword_hits = sum(1 for keyword in keywords if keyword in text_lower)
            keyword_score = keyword_hits / len(keywords) if keywords else 0.0
            combined_score = 0.8 * semantic_score + 0.2 * keyword_score

            result = {
                "chunk_id": chunk["chunk_id"],
                "page": chunk["page"],
                "text": chunk["text"],
                "score": semantic_score,
                "keyword_score": keyword_score,
                "combined_score": combined_score,
            }
            results.append(result)
            print(
                f"  [{int(index):2d}] {chunk['chunk_id']} (Page {chunk['page']}) "
                f"semantic={semantic_score:.3f} keyword={keyword_score:.3f} combined={combined_score:.3f}"
            )

        results.sort(key=lambda item: item.get("combined_score", item.get("score", 0)), reverse=True)
        print(f"✅ Retrieved {len(results)} candidate chunk(s)")
        return results
