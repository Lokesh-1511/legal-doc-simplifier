"""
Lightweight semantic retrieval using Hugging Face embeddings + scikit-learn cosine similarity.
No local models, no PyTorch, no heavy dependencies.
"""

from typing import Dict, List
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from .embeddings_hf import get_hf_embeddings


class SemanticRetriever:
    """
    In-memory semantic retriever using Hugging Face embeddings + cosine similarity.
    
    Lightweight alternative to local models that avoids PyTorch/CUDA.
    Embeddings are fetched from Hugging Face's hosted inference API.
    """

    def __init__(self) -> None:
        self.chunks: List[Dict[str, object]] = []
        self.embeddings: np.ndarray | None = None

    def build_index(self, chunks: List[Dict[str, object]]) -> None:
        """
        Embed all chunks using Hugging Face API and store embeddings.
        
        Args:
            chunks: List of chunk dicts with 'text', 'page', 'chunk_id'.
        """
        self.chunks = chunks
        if not chunks:
            self.embeddings = None
            print("⚠️  No chunks to index")
            return

        texts = [str(chunk["text"]) for chunk in chunks]
        print(f"🔍 Indexing {len(chunks)} chunks...")
        
        try:
            # Call Hugging Face API for embeddings
            self.embeddings = get_hf_embeddings(texts)
            print(f"✅ Index built successfully")
        except Exception as e:
            print(f"❌ Embedding error: {e}")
            self.embeddings = None

    def search(self, query: str, top_k: int = 4) -> List[Dict[str, object]]:
        """
        Retrieve top-k chunks most similar to query.
        
        Args:
            query: User question/search text.
            top_k: Number of chunks to retrieve.
        
        Returns:
            List of chunk dicts with similarity scores, sorted by relevance.
        """
        if not query.strip() or not self.chunks or self.embeddings is None:
            return []

        print(f"🔎 Searching for: '{query}'")
        
        try:
            # Get query embedding from Hugging Face API
            query_embedding = get_hf_embeddings([query])
        except Exception as e:
            print(f"❌ Query embedding error: {e}")
            return []

        # Compute cosine similarity
        similarities = cosine_similarity(query_embedding, self.embeddings)[0]
        
        print(f"📊 Similarity scores: min={similarities.min():.3f}, max={similarities.max():.3f}, avg={similarities.mean():.3f}")

        top_k = max(1, min(top_k, len(self.chunks)))
        ranked_indices = np.argsort(similarities)[::-1][:top_k]

        results: List[Dict[str, object]] = []
        for idx in ranked_indices:
            chunk = self.chunks[int(idx)]
            score = float(similarities[int(idx)])
            results.append(
                {
                    "chunk_id": chunk["chunk_id"],
                    "page": chunk["page"],
                    "text": chunk["text"],
                    "score": score,
                }
            )
            print(f"  ✓ {chunk['chunk_id']} (Page {chunk['page']}) - similarity: {score:.3f}")
        
        return results
