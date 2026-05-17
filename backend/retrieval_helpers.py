"""
Lightweight semantic retrieval helpers for RAG.

Philosophy:
- Primary signal: Semantic similarity (Hugging Face embeddings + cosine distance)
- Secondary signal: Keyword overlap for tie-breaking
- Avoid: Large manually-hardcoded synonym dictionaries

Why semantic-first matters:
- Embeddings capture meaning: "maintenance obligation" matches "repair responsibility"
  without needing handcrafted legal thesaurus
- Scales naturally: New terminology learned through embeddings, not manual updates
- Less brittle: Doesn't break on domain-specific jargon outside training data
- More realistic: Modern RAG systems rely on semantic retrieval, not rule engines

Keyword re-ranking still useful:
- Breaks ties when multiple chunks have similar semantic scores
- Boosts chunks explicitly mentioning query terms (user signal)
- Light touch: 20% weight, semantic similarity dominates (80%)
"""

from typing import Dict, List
import re


def normalize_query(query: str) -> str:
    """
    Light normalization of user query.
    
    Simple cleaning without heavy NLP:
    - Trim whitespace
    - Lowercase consistency
    - Remove excessive punctuation
    
    Why NOT expand with synonyms?
    - Embeddings already capture synonymy better than handcrafted rules
    - "tenant obligations" and "landlord duties" are close in embedding space
    - Adding manual synonym lists introduces brittleness and maintenance burden
    - Real-world RAG systems rely on embeddings, not rule-based expansion
    
    Args:
        query: Raw user input.
    
    Returns:
        Normalized query string.
    """
    # Strip whitespace
    normalized = query.strip()
    
    # Lowercase for consistent matching
    normalized = normalized.lower()
    
    # Remove excessive punctuation (but keep apostrophes in contractions)
    # Replace multiple punctuation marks with single space
    normalized = re.sub(r'[?!]{2,}', '?', normalized)  # ??, !!, ??! → ?
    normalized = re.sub(r'\s+', ' ', normalized)  # Multiple spaces → single
    
    return normalized


def extract_keywords(query: str) -> set:
    """
    Extract important keywords from query.
    Used only for lightweight re-ranking, not as primary retrieval signal.
    
    Why this simple approach?
    - Embeddings are the primary retrieval mechanism
    - Keywords only help break ties between similar-scoring chunks
    - Simple keyword extraction (stopword removal) is sufficient
    - Avoids heavy NLP (no stemming, lemmatization, POS tagging)
    
    Args:
        query: Normalized user question.
    
    Returns:
        Set of non-stopword tokens >2 chars.
    """
    # Simple stopwords (common English words with little semantic value)
    stopwords = {
        'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
        'and', 'or', 'not', 'no', 'if', 'what', 'how', 'why', 'when', 'where',
        'who', 'which', 'that', 'this', 'these', 'those', 'can', 'could', 'will',
        'would', 'should', 'may', 'might', 'must', 'do', 'does', 'did', 'have',
        'has', 'having', 'of', 'in', 'on', 'at', 'by', 'to', 'for', 'with', 'about'
    }
    
    # Extract words
    words = re.findall(r'\b\w+\b', query.lower())
    
    # Filter stopwords and short tokens
    keywords = {w for w in words if w not in stopwords and len(w) > 2}
    
    return keywords


def rerank_chunks_by_keywords(chunks: List[Dict], query: str) -> List[Dict]:
    """
    Light re-ranking of semantically retrieved chunks using keyword overlap.
    
    Hybrid scoring for tie-breaking:
    combined_score = 0.8 * semantic_similarity + 0.2 * keyword_overlap
    
    Why keep keyword re-ranking?
    - Multiple chunks may have similar semantic scores (e.g., both discuss rent)
    - Keyword overlap breaks ties: Chunk with "rent amount" beats "rental property"
      when query explicitly mentions "amount"
    - User signal: If user typed a word, they probably care about it
    - No heavy machinery: Simple substring matching, no heavy NLP
    
    Why NOT large synonym mapping?
    - Embeddings already handle synonymy ("tenant duty" ~ "landlord obligation")
    - Rule-based mapping is brittle and hard to maintain
    - Real RAG systems rely on embeddings for semantic matching
    - This simple hybrid is sufficient for tie-breaking
    
    Args:
        chunks: List of retrieved chunks with 'text' and 'score' keys.
        query: User's original question.
    
    Returns:
        Chunks with combined_score field, sorted by relevance.
    """
    if not chunks or not query:
        return chunks
    
    keywords = extract_keywords(query)
    if not keywords:
        # No keywords extracted, return original order
        return chunks
    
    # Calculate keyword overlap for each chunk
    for chunk in chunks:
        text_lower = chunk['text'].lower()
        
        # Count how many query keywords appear in chunk
        keyword_matches = sum(1 for kw in keywords if kw in text_lower)
        
        # Normalize: 0-1 scale (percentage of query keywords matched)
        keyword_score = keyword_matches / len(keywords) if keywords else 0
        
        # Combine semantic (primary) + keyword (tie-breaker)
        semantic_score = chunk.get('score', 0)
        combined = 0.8 * semantic_score + 0.2 * keyword_score
        
        chunk['combined_score'] = combined
    
    # Re-rank by combined score
    reranked = sorted(chunks, key=lambda x: x.get('combined_score', 0), reverse=True)
    return reranked


def format_context_block(chunks: List[Dict]) -> str:
    """
    Format multiple retrieved chunks into readable context block.
    Separates chunks clearly with page references.
    
    Example output:
    ---
    [PAGE 2, CHUNK 1]
    The lease term shall be...
    
    [PAGE 5, CHUNK 2]
    Either party may terminate...
    ---
    
    Args:
        chunks: List of retrieved chunks with 'text', 'page', 'chunk_id'.
    
    Returns:
        Formatted context string ready for LLM.
    """
    if not chunks:
        return ""
    
    formatted_chunks = []
    for i, chunk in enumerate(chunks, 1):
        chunk_text = chunk.get('text', '').strip()
        page = chunk.get('page', '?')
        chunk_id = chunk.get('chunk_id', f'chunk-{i}')
        
        # Only show similarity score in development if available
        score_info = ""
        if 'combined_score' in chunk:
            score_info = f" [relevance: {chunk['combined_score']:.1%}]"
        elif 'score' in chunk:
            score_info = f" [similarity: {chunk['score']:.1%}]"
        
        formatted = f"[PAGE {page} - {chunk_id}]{score_info}\n{chunk_text}"
        formatted_chunks.append(formatted)
    
    return "\n\n---\n\n".join(formatted_chunks)
