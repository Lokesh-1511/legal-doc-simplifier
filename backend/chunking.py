from typing import Dict, List


def _normalize_whitespace(text: str) -> str:
    return " ".join(text.split())


def chunk_pages(
    pages: List[Dict[str, object]],
    chunk_size: int = 180,
    overlap: int = 40,
) -> List[Dict[str, object]]:
    """Split page text into overlapping word chunks while preserving page numbers."""
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
    chunk_size: int = 180,
    overlap: int = 40,
) -> List[Dict[str, object]]:
    """Chunk plain text as a single pseudo-page (Page 1)."""
    return chunk_pages([{"page": 1, "text": text}], chunk_size=chunk_size, overlap=overlap)
