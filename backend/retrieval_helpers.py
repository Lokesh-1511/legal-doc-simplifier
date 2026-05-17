"""
Lightweight helper utilities for semantic retrieval.

This module intentionally stays small. The heavy lifting belongs to embeddings
and, when needed, an LLM reranker. The helpers here only do light normalization
and keyword extraction so the retrieval pipeline remains understandable.
"""

from typing import Set
import re


def normalize_query(query: str) -> str:
    """
    Apply minimal query cleanup.

    We keep this light because semantic embeddings already handle meaning.
    Over-normalizing or rewriting the user's wording with manual rules makes the
    system brittle and harder to explain.
    """
    normalized = query.strip().lower()
    normalized = re.sub(r'[?!]{2,}', '?', normalized)
    normalized = re.sub(r'\s+', ' ', normalized)
    return normalized


def extract_keywords(query: str) -> Set[str]:
    """
    Extract a small set of keywords for lightweight reranking.

    This does not try to understand legal semantics. It only provides a small
    lexical signal that can help break ties between semantically similar chunks.
    """
    stopwords = {
        'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
        'and', 'or', 'not', 'no', 'if', 'what', 'how', 'why', 'when', 'where',
        'who', 'which', 'that', 'this', 'these', 'those', 'can', 'could', 'will',
        'would', 'should', 'may', 'might', 'must', 'do', 'does', 'did', 'have',
        'has', 'having', 'of', 'in', 'on', 'at', 'by', 'to', 'for', 'with', 'about'
    }
    words = re.findall(r'\b\w+\b', query.lower())
    return {word for word in words if word not in stopwords and len(word) > 2}
