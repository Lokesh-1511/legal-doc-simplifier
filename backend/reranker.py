"""
Hybrid retrieval reranking utilities.

The retriever finds candidate chunks using embeddings.
The reranker uses a lightweight LLM step to choose the best evidence.
This is useful for short or ambiguous legal questions where embeddings alone
can return chunks that are semantically close but not actually answer-bearing.
"""

from __future__ import annotations

import re
from typing import Dict, List, Tuple, Optional

from .prompts import build_rerank_prompt


def format_context_block(chunks: List[Dict[str, object]]) -> str:
    """Format retrieved chunks into a clear context block for the LLM."""
    if not chunks:
        return ""

    formatted_chunks = []
    for index, chunk in enumerate(chunks, 1):
        page = chunk.get("page", "?")
        chunk_id = chunk.get("chunk_id", f"chunk-{index}")
        score = chunk.get("combined_score", chunk.get("score", 0))
        text = str(chunk.get("text", "")).strip()
        formatted_chunks.append(
            f"[Page {page} | {chunk_id} | relevance {float(score):.3f}]\n{text}"
        )

    return "\n\n---\n\n".join(formatted_chunks)


def _truncate_text(text: str, max_chars: int = 320) -> str:
    text = " ".join(text.split())
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3].rstrip() + "..."


def _parse_rerank_order(raw_output: str, candidate_count: int) -> List[int]:
    numbers = []
    for match in re.findall(r"\d+", raw_output):
        value = int(match)
        if 1 <= value <= candidate_count and value not in numbers:
            numbers.append(value)
    return numbers


def llm_rerank_chunks(
    question: str,
    candidates: List[Dict[str, object]],
    groq_client,
    model_name: str,
    max_selected: int = 5,
) -> Tuple[List[Dict[str, object]], Dict[str, object]]:
    """
    Ask the LLM to rank the most relevant chunks among retrieval candidates.

    This is intentionally lightweight: the LLM only selects evidence. The actual
    document understanding still comes from embeddings plus cosine similarity.
    """
    if not candidates:
        return [], {"mode": "empty"}

    # If the LLM is unavailable, keep the semantic ranking.
    if groq_client is None:
        selected = candidates[:max_selected]
        return selected, {"mode": "semantic_only", "selected_count": len(selected)}

    candidate_lines = []
    for index, chunk in enumerate(candidates, 1):
        page = chunk.get("page", "?")
        score = float(chunk.get("combined_score", chunk.get("score", 0)))
        text = _truncate_text(str(chunk.get("text", "")))
        candidate_lines.append(
            f"{index}. chunk_id={chunk.get('chunk_id')} | page={page} | score={score:.3f} | text={text}"
        )

    prompt = build_rerank_prompt(question, "\n".join(candidate_lines))

    try:
        response = groq_client.chat.completions.create(
            model=model_name,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You rank legal evidence chunks. Choose only the chunks that "
                        "most directly support answering the question."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0,
            max_tokens=120,
        )
        raw_output = response.choices[0].message.content.strip()
        order = _parse_rerank_order(raw_output, len(candidates))

        if not order:
            selected = candidates[:max_selected]
            return selected, {
                "mode": "fallback_parse",
                "raw_output": raw_output,
                "selected_count": len(selected),
            }

        selected = []
        for item in order:
            selected.append(candidates[item - 1])
            if len(selected) >= max_selected:
                break

        for rank, chunk in enumerate(selected, 1):
            chunk["llm_rank"] = rank

        return selected, {
            "mode": "llm_rerank",
            "raw_output": raw_output,
            "selected_count": len(selected),
            "selected_order": order,
        }
    except Exception as error:
        selected = candidates[:max_selected]
        return selected, {"mode": "error_fallback", "error": str(error), "selected_count": len(selected)}


def source_pages_label(chunks: List[Dict[str, object]]) -> str:
    pages = sorted({int(chunk.get("page", 0)) for chunk in chunks if str(chunk.get("page", "")).isdigit() or isinstance(chunk.get("page"), int)})
    if not pages:
        return "Source: Pages unknown"
    if len(pages) == 1:
        return f"Source: Page {pages[0]}"
    return "Source: Pages " + ", ".join(str(page) for page in pages)
