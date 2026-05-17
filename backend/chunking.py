from typing import Dict, List


def _normalize_whitespace(text: str) -> str:
    return " ".join(text.split())


def chunk_pages(
    pages: List[Dict[str, object]],
    chunk_size: int = 500,
    overlap: int = 100,
) -> List[Dict[str, object]]:
    """
    Split page text into overlapping word chunks while preserving page numbers.
    
    Chunk Strategy:
    - chunk_size=500 words: Large enough to preserve legal clause structure.
                            A typical legal clause (condition, obligation, etc.)
                            is 50-200 words, so 500-word chunks keep related
                            concepts together and provide good context to the LLM.
    
    - overlap=100 words: 20% overlap ensures important concepts at chunk boundaries
                         are repeated, so semantically similar queries match chunks
                         better. Example: "lease term" might appear at the end of
                         one chunk and beginning of next, so both are indexed.
    
    Why it matters:
    - Small chunks (180 words) lose context: "The tenant shall maintain the
      property in good condition" might split the responsibility from examples.
    - Large chunks (1000+) hurt retrieval: Too much noise, cosine similarity
      becomes less precise.
    - Optimal for legal docs: 400-600 words balances context preservation with
      retrieval precision.
    
    Args:
        pages: List of page dicts with 'page' and 'text' keys.
        chunk_size: Number of words per chunk (default 500 = ~2000-2500 chars).
        overlap: Number of words to repeat between chunks (default 100 = 20%).
    
    Returns:
        List of chunk dicts: {chunk_id, page, text}
    """
    if chunk_size <= overlap:
        raise ValueError("chunk_size must be greater than overlap")

    chunks: List[Dict[str, object]] = []
    step = chunk_size - overlap

    for page_data in pages:
        page_number = int(page_data["page"])
        text = _normalize_whitespace(str(page_data.get("text", "")))
        if not text:
            continue

        words = text.split()
        chunk_counter = 1

        for start in range(0, len(words), step):
            end = min(start + chunk_size, len(words))
            chunk_text = " ".join(words[start:end]).strip()
            if not chunk_text:
                continue

            chunks.append(
                {
                    "chunk_id": f"p{page_number}-c{chunk_counter}",
                    "page": page_number,
                    "text": chunk_text,
                }
            )
            chunk_counter += 1

            if end >= len(words):
                break

    return chunks


def chunk_plain_text(
    text: str,
    chunk_size: int = 500,
    overlap: int = 100,
) -> List[Dict[str, object]]:
    """
    Chunk plain text as a single pseudo-page (Page 1).
    Uses same strategy as chunk_pages() for consistency.
    """
    return chunk_pages([{"page": 1, "text": text}], chunk_size=chunk_size, overlap=overlap)
