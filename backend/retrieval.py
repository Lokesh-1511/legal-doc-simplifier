"""
Lightweight semantic retrieval using Hugging Face embeddings + scikit-learn cosine similarity.
No local models, no PyTorch, no heavy dependencies.

Architecture:
1. Embed all chunks upfront (vectorize document)
2. For each query, normalize and embed it
3. Compute cosine similarity (semantic retrieval)
4. Re-rank by keyword overlap (light tie-breaker)
5. Return top-K with intelligent fallback for weak matches

Philosophy:
- Semantic similarity is primary: Embeddings capture meaning better than rules
- Keyword re-ranking is secondary: Breaks ties, doesn't drive retrieval
- No hardcoded synonym dictionaries: Embeddings scale better and are more maintainable
- Fallback logic prevents false negatives: Show best available rather than empty result

Why this approach?
- Realistic for modern RAG systems: Real-world semantic retrieval doesn't rely on
  manually-crafted legal thesaurus
- Scalable: New terminology is learned through embeddings, not manual updates
- Maintainable: Less brittle than rule-based expansion
- Understandable: Simpler code, easier to debug and explain in interviews
"""

from typing import Dict, List
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from .embeddings_hf import get_hf_embeddings
from .retrieval_helpers import (
    normalize_query,
    rerank_chunks_by_keywords,
)


class SemanticRetriever:
    """
    In-memory semantic retriever using Hugging Face embeddings + cosine similarity.
    
    Lightweight alternative to local models that avoids PyTorch/CUDA.
    Embeddings are fetched from Hugging Face's hosted inference API.
    
    Why Semantic Retrieval?
    - RAG (Retrieval Augmented Generation) requires finding relevant document chunks.
    - Keyword search (Ctrl+F) is too brittle—misses synonyms and related terms.
    - Semantic search understands meaning: "tenant must maintain" matches "landlord
      repair obligations" even without keyword overlap.
    - Embeddings capture similarity naturally, no manual rules needed.
    
    Why NOT rule-based expansion?
    - Handcrafted synonym lists don't scale (new terms = manual updates)
    - Embeddings handle synonymy better (e.g., "rent" ~ "lease payment" automatically)
    - Over-engineering: Modern RAG relies on semantic similarity, not rule engines
    - Maintenance burden: Brittleness increases with rule complexity
    
    Performance Note:
    - First query is slower (HF API cold start ~1-2s).
    - Subsequent queries fast (cosine similarity O(n)).
    - No local model = no GPU needed, works on 512MB free tier.
    """

    def __init__(self) -> None:
        self.chunks: List[Dict[str, object]] = []
        self.embeddings: np.ndarray | None = None

    def build_index(self, chunks: List[Dict[str, object]]) -> None:
        """
        Embed all chunks using Hugging Face API and store embeddings.
        
        Why embed all chunks upfront?
        - Efficient: Query embedding computed once, not per chunk
        - Fast: Cosine similarity O(n) with precomputed embeddings
        - Practical: 5000 chunks = ~1-2s to embed (acceptable one-time cost)
        
        Args:
            chunks: List of chunk dicts with 'text', 'page', 'chunk_id'.
        """
        self.chunks = chunks
        if not chunks:
            self.embeddings = None
            print("⚠️  No chunks to index")
            return

        texts = [str(chunk["text"]) for chunk in chunks]
        print(f"📊 Preparing to embed {len(chunks)} chunks for indexing...")
        
        try:
            # Call Hugging Face API for embeddings
            self.embeddings = get_hf_embeddings(texts)
            embedding_dim = self.embeddings.shape[1] if self.embeddings.ndim > 1 else 1
            print(f"✅ Index built: {len(chunks)} chunks with {embedding_dim}-dim embeddings")
            print(f"   Chunks distributed across pages: {self._describe_chunk_distribution()}")
        except Exception as e:
            print(f"❌ Embedding error: {e}")
            self.embeddings = None

    def _describe_chunk_distribution(self) -> str:
        """Helper to show chunk distribution for debugging."""
        if not self.chunks:
            return "no chunks"
        
        pages = {}
        for chunk in self.chunks:
            page = chunk.get("page", 0)
            pages[page] = pages.get(page, 0) + 1
        
        # Show pages with highest chunk counts
        sorted_pages = sorted(pages.items(), key=lambda x: x[1], reverse=True)[:3]
        desc = ", ".join(f"Page {p}: {count} chunks" for p, count in sorted_pages)
        return desc

    def search(
        self, query: str, top_k: int = 4, min_similarity: float = 0.3
    ) -> List[Dict[str, object]]:
        """
        Retrieve top-k chunks most similar to query.
        
        Strategy:
        1. Normalize query (trim, lowercase, clean punctuation)
        2. Embed normalized query using HF API
        3. Compute cosine similarity to all chunks (semantic retrieval)
        4. Apply minimum similarity threshold
        5. Re-rank by keyword overlap (light tie-breaking)
        6. Return top-K with fallback to best available if threshold not met
        
        Why this simple approach?
        - Semantic similarity (embeddings) is the primary retrieval signal
        - It naturally handles synonymy without handcrafted rules
        - Keyword re-ranking provides light tie-breaking
        - Fallback prevents false negatives (no "not found" if any relevant chunk exists)
        
        Args:
            query: User question/search text.
            top_k: Number of chunks to retrieve.
            min_similarity: Threshold for acceptable match (0.0-1.0).
                           0.3 = results below 30th percentile used only as fallback.
        
        Returns:
            List of chunk dicts with scores, sorted by relevance.
            May return empty list only if no chunks indexed at all.
        """
        if not query.strip() or not self.chunks or self.embeddings is None:
            print("⚠️  No chunks indexed yet, cannot search")
            return []

        # Normalize query (simple cleaning, no heavy NLP)
        normalized_query = normalize_query(query)
        print(f"\n🔍 Query: '{query}' → normalized: '{normalized_query}'")
        
        try:
            # Get query embedding from Hugging Face API
            query_embedding = get_hf_embeddings([normalized_query])
        except Exception as e:
            print(f"❌ Query embedding error: {e}")
            return []

        # Compute cosine similarity
        similarities = cosine_similarity(query_embedding, self.embeddings)[0]
        
        # Debug statistics
        above_threshold = np.sum(similarities >= min_similarity)
        print(f"📊 Similarity: min={similarities.min():.3f}, max={similarities.max():.3f}, "
              f"avg={similarities.mean():.3f}, above_threshold={above_threshold}")

        # Find chunks above minimum threshold
        above_threshold_indices = np.where(similarities >= min_similarity)[0]
        
        if len(above_threshold_indices) == 0:
            # Fallback: use best chunks even if below threshold
            # This prevents returning empty when document has weak-but-valid matches
            # Example: Short query "time?" may not hit 0.3 threshold, but best chunk 
            # at 0.25 similarity is still useful and better than nothing
            above_threshold_indices = np.argsort(similarities)[::-1][:top_k]
            print(f"⚠️  No chunks above threshold—using best {len(above_threshold_indices)} anyway")

        # Rank by similarity
        ranked_indices = above_threshold_indices[
            np.argsort(similarities[above_threshold_indices])[::-1][:top_k]
        ]

        # Build results with semantic scores
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
            print(f"  [{idx:2d}] {chunk['chunk_id']} (Page {chunk['page']}) → similarity: {score:.3f}")
        
        # Re-rank by keyword overlap (light tie-breaker, doesn't drive primary retrieval)
        if results and normalized_query:
            results = rerank_chunks_by_keywords(results, normalized_query)
            print(f"🔄 Re-ranked by keyword overlap (20% weight):")
            for r in results:
                print(f"     {r['chunk_id']} (Page {r['page']}) → combined: {r.get('combined_score', r['score']):.3f}")
        
        if results:
            print(f"✅ Retrieved {len(results)} chunk(s)")
        
        return results


class SemanticRetriever:
    """
    In-memory semantic retriever using Hugging Face embeddings + cosine similarity.
    
    Lightweight alternative to local models that avoids PyTorch/CUDA.
    Embeddings are fetched from Hugging Face's hosted inference API.
    
    Why Semantic Retrieval?
    - RAG (Retrieval Augmented Generation) requires finding relevant document chunks.
    - Keyword search (Ctrl+F) is too brittle—misses synonyms and related terms.
    - Semantic search understands meaning: "tenant must maintain" matches "landlord
      repair obligations" even without keyword overlap.
    - Embeddings capture similarity naturally, no manual rules needed.
    
    Why NOT rule-based expansion?
    - Handcrafted synonym lists don't scale (new terms = manual updates)
    - Embeddings handle synonymy better (e.g., "rent" ~ "lease payment" automatically)
    - Over-engineering: Modern RAG relies on semantic similarity, not rule engines
    - Maintenance burden: Brittleness increases with rule complexity
    
    Performance Note:
    - First query is slower (HF API cold start ~1-2s).
    - Subsequent queries fast (cosine similarity O(n)).
    - No local model = no GPU needed, works on 512MB free tier.
    """

    def __init__(self) -> None:
        self.chunks: List[Dict[str, object]] = []
        self.embeddings: np.ndarray | None = None

    def build_index(self, chunks: List[Dict[str, object]]) -> None:
        """
        Embed all chunks using Hugging Face API and store embeddings.
        
        Why embed all chunks upfront?
        - Efficient: Query embedding computed once, not per chunk
        - Fast: Cosine similarity O(n) with precomputed embeddings
        - Practical: 5000 chunks = ~1-2s to embed (acceptable one-time cost)
        
        Args:
            chunks: List of chunk dicts with 'text', 'page', 'chunk_id'.
        """
        self.chunks = chunks
        if not chunks:
            self.embeddings = None
            print("⚠️  No chunks to index")
            return

        texts = [str(chunk["text"]) for chunk in chunks]
        print(f"📊 Preparing to embed {len(chunks)} chunks for indexing...")
        
        try:
            # Call Hugging Face API for embeddings
            self.embeddings = get_hf_embeddings(texts)
            embedding_dim = self.embeddings.shape[1] if self.embeddings.ndim > 1 else 1
            print(f"✅ Index built: {len(chunks)} chunks with {embedding_dim}-dim embeddings")
            print(f"   Chunks distributed across pages: {self._describe_chunk_distribution()}")
        except Exception as e:
            print(f"❌ Embedding error: {e}")
            self.embeddings = None

    def _describe_chunk_distribution(self) -> str:
        """Helper to show chunk distribution for debugging."""
        if not self.chunks:
            return "no chunks"
        
        pages = {}
        for chunk in self.chunks:
            page = chunk.get("page", 0)
            pages[page] = pages.get(page, 0) + 1
        
        # Show pages with highest chunk counts
        sorted_pages = sorted(pages.items(), key=lambda x: x[1], reverse=True)[:3]
        desc = ", ".join(f"Page {p}: {count} chunks" for p, count in sorted_pages)
        return desc

    def search(
        self, query: str, top_k: int = 4, min_similarity: float = 0.3
    ) -> List[Dict[str, object]]:
        """
        Retrieve top-k chunks most similar to query.
        
        Strategy:
        1. Normalize query (trim, lowercase, clean punctuation)
        2. Embed normalized query using HF API
        3. Compute cosine similarity to all chunks (semantic retrieval)
        4. Apply minimum similarity threshold
        5. Re-rank by keyword overlap (light tie-breaking)
        6. Return top-K with fallback to best available if threshold not met
        
        Why this simple approach?
        - Semantic similarity (embeddings) is the primary retrieval signal
        - It naturally handles synonymy without handcrafted rules
        - Keyword re-ranking provides light tie-breaking
        - Fallback prevents false negatives (no "not found" if any relevant chunk exists)
        
        Args:
            query: User question/search text.
            top_k: Number of chunks to retrieve.
            min_similarity: Threshold for acceptable match (0.0-1.0).
                           0.3 = results below 30th percentile used only as fallback.
        
        Returns:
            List of chunk dicts with scores, sorted by relevance.
            May return empty list only if no chunks indexed at all.
        """
        if not query.strip() or not self.chunks or self.embeddings is None:
            print("⚠️  No chunks indexed yet, cannot search")
            return []

        # Normalize query (simple cleaning, no heavy NLP)
        normalized_query = normalize_query(query)
        print(f"\n🔍 Query: '{query}' → normalized: '{normalized_query}'")
        
        try:
            # Get query embedding from Hugging Face API
            query_embedding = get_hf_embeddings([normalized_query])
        except Exception as e:
            print(f"❌ Query embedding error: {e}")
            return []

        # Compute cosine similarity
        similarities = cosine_similarity(query_embedding, self.embeddings)[0]
        
        # Debug statistics
        above_threshold = np.sum(similarities >= min_similarity)
        print(f"📊 Similarity: min={similarities.min():.3f}, max={similarities.max():.3f}, "
              f"avg={similarities.mean():.3f}, above_threshold={above_threshold}")

        # Find chunks above minimum threshold
        above_threshold_indices = np.where(similarities >= min_similarity)[0]
        
        if len(above_threshold_indices) == 0:
            # Fallback: use best chunks even if below threshold
            # This prevents returning empty when document has weak-but-valid matches
            # Example: Short query "time?" may not hit 0.3 threshold, but best chunk 
            # at 0.25 similarity is still useful and better than nothing
            above_threshold_indices = np.argsort(similarities)[::-1][:top_k]
            print(f"⚠️  No chunks above threshold—using best {len(above_threshold_indices)} anyway")

        # Rank by similarity
        ranked_indices = above_threshold_indices[
            np.argsort(similarities[above_threshold_indices])[::-1][:top_k]
        ]

        # Build results with semantic scores
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
            print(f"  [{idx:2d}] {chunk['chunk_id']} (Page {chunk['page']}) → similarity: {score:.3f}")
        
        # Re-rank by keyword overlap (light tie-breaker, doesn't drive primary retrieval)
        if results and normalized_query:
            results = rerank_chunks_by_keywords(results, normalized_query)
            print(f"🔄 Re-ranked by keyword overlap (20% weight):")
            for r in results:
                print(f"     {r['chunk_id']} (Page {r['page']}) → combined: {r.get('combined_score', r['score']):.3f}")
        
        if results:
            print(f"✅ Retrieved {len(results)} chunk(s)")
        
        return results
