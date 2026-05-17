"""
Hierarchical document summarization for large legal PDFs.

Why direct prompting fails for large documents:
- The entire document can exceed the model context window
- Long prompts are expensive and unstable
- Important clauses get diluted in a huge text block

This module uses a map-reduce approach:
1. Direct summary for small documents
2. Chunk summaries for large documents
3. Merged summaries for the final answer
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

from .chunking import chunk_pages, chunk_plain_text
from .prompts import build_chunk_summary_prompt, build_direct_summary_prompt, build_reduce_summary_prompt


@dataclass
class SummaryResult:
    summary: str
    strategy: str
    estimated_tokens: int
    chunk_count: int
    chunk_summaries: int


class DocumentSummarizer:
    def __init__(
        self,
        direct_token_limit: int = 1200,
        chunk_size: int = 500,
        overlap: int = 100,
        batch_size: int = 4,
    ) -> None:
        self.direct_token_limit = direct_token_limit
        self.chunk_size = chunk_size
        self.overlap = overlap
        self.batch_size = batch_size

    @staticmethod
    def estimate_tokens(text: str) -> int:
        # Rough estimate: ~1.3 tokens per word is usually good enough for routing.
        return max(1, int(len(text.split()) * 1.3))

    def is_small_document(self, text: str) -> bool:
        return self.estimate_tokens(text) <= self.direct_token_limit

    def summarize(
        self,
        text: str,
        level: str,
        groq_client,
        pages: Optional[List[Dict[str, object]]] = None,
        model_name: str = "llama-3.3-70b-versatile",
    ) -> SummaryResult:
        estimated_tokens = self.estimate_tokens(text)
        if self.is_small_document(text):
            print(f"📄 Small document detected (~{estimated_tokens} tokens). Using direct summarization.")
            summary = self._direct_summary(text, level, groq_client, model_name)
            return SummaryResult(
                summary=summary,
                strategy="direct",
                estimated_tokens=estimated_tokens,
                chunk_count=1,
                chunk_summaries=1,
            )

        print(f"📚 Large document detected (~{estimated_tokens} tokens). Using hierarchical summarization.")
        if pages is not None and pages:
            chunks = chunk_pages(pages, chunk_size=self.chunk_size, overlap=self.overlap)
        else:
            chunks = chunk_plain_text(text, chunk_size=self.chunk_size, overlap=self.overlap)

        print(f"🔹 Split document into {len(chunks)} chunks for map-reduce summarization.")
        for index, chunk in enumerate(chunks[:3], 1):
            preview = " ".join(str(chunk.get("text", "")).split()[:24])
            print(f"   chunk {index}: page {chunk.get('page')} | {preview}...")

        if not chunks:
            print("⚠️ No chunks produced. Falling back to direct summarization.")
            summary = self._direct_summary(text, level, groq_client, model_name)
            return SummaryResult(
                summary=summary,
                strategy="direct_fallback",
                estimated_tokens=estimated_tokens,
                chunk_count=0,
                chunk_summaries=0,
            )

        chunk_summaries: List[str] = []
        for index, chunk in enumerate(chunks, 1):
            print(f"   ↳ summarizing chunk {index}/{len(chunks)} (Page {chunk.get('page')})")
            chunk_summary = self._summarize_chunk(chunk, groq_client, model_name)
            if chunk_summary:
                chunk_summaries.append(chunk_summary)

        if not chunk_summaries:
            print("⚠️ Chunk summarization failed. Falling back to direct summary.")
            summary = self._direct_summary(text, level, groq_client, model_name)
            return SummaryResult(
                summary=summary,
                strategy="chunk_failure_fallback",
                estimated_tokens=estimated_tokens,
                chunk_count=len(chunks),
                chunk_summaries=0,
            )

        reduced_summary = self._reduce_summaries(chunk_summaries, level, groq_client, model_name)
        return SummaryResult(
            summary=reduced_summary,
            strategy="hierarchical",
            estimated_tokens=estimated_tokens,
            chunk_count=len(chunks),
            chunk_summaries=len(chunk_summaries),
        )

    def _direct_summary(self, text: str, level: str, groq_client, model_name: str) -> str:
        if groq_client is None:
            return "⚠️ GROQ_API_KEY is missing. Add it to .env to enable summarization."

        prompt = build_direct_summary_prompt(level, text)
        response = groq_client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": "You summarize legal text faithfully and concisely."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
            max_tokens=900,
        )
        return response.choices[0].message.content.strip()

    def _summarize_chunk(self, chunk: Dict[str, object], groq_client, model_name: str) -> str:
        if groq_client is None:
            return ""

        prompt = build_chunk_summary_prompt(
            page=int(chunk.get("page", 0)),
            chunk_id=str(chunk.get("chunk_id", "chunk")),
            chunk_text=str(chunk.get("text", "")),
        )
        response = groq_client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": "Summarize the chunk without adding outside information."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
            max_tokens=220,
        )
        return response.choices[0].message.content.strip()

    def _reduce_summaries(self, chunk_summaries: List[str], level: str, groq_client, model_name: str) -> str:
        if groq_client is None:
            return "⚠️ GROQ_API_KEY is missing. Add it to .env to enable summarization."

        # Hierarchical reduction keeps prompts compact and prevents token overflow.
        stage = list(chunk_summaries)
        while len(stage) > 1:
            next_stage: List[str] = []
            for start in range(0, len(stage), self.batch_size):
                batch = stage[start:start + self.batch_size]
                batch_context = "\n\n".join(f"- {item}" for item in batch)
                prompt = build_reduce_summary_prompt(level, batch_context)
                response = groq_client.chat.completions.create(
                    model=model_name,
                    messages=[
                        {"role": "system", "content": "Merge legal summaries faithfully and remove repetition."},
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.2,
                    max_tokens=700,
                )
                next_stage.append(response.choices[0].message.content.strip())
            stage = next_stage
            print(f"🔸 Reduction stage complete. {len(stage)} summary block(s) remain.")

        final_prompt = build_reduce_summary_prompt(level, f"- {stage[0]}")
        final_response = groq_client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": "Write the final legal summary strictly from the provided notes."},
                {"role": "user", "content": final_prompt},
            ],
            temperature=0.2,
            max_tokens=900,
        )
        return final_response.choices[0].message.content.strip()
