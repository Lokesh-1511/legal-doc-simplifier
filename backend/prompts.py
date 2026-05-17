"""
Compact prompt templates for summarization, reranking, and QA.

These prompts are intentionally short because token budget matters more than
fancy wording when we want stable, low-cost LLM behavior.
"""

SUMMARY_LEVELS = {
    "Quick Summary (ELI5)": {
        "direct": (
            "You are a legal document explainer. Explain the text in very simple "
            "language for a beginner. Focus on the main idea, rights, duties, "
            "dates, money, and risks. Keep it short and clear.\n\nTEXT:\n{text}\n\nSUMMARY:"
        ),
        "reduce": (
            "You are combining chunk summaries into one ELI5 legal summary. "
            "Remove repetition, keep only the most important points, and use "
            "simple language. Keep page references when helpful.\n\nCHUNK SUMMARIES:\n{context}\n\nFINAL SUMMARY:"
        ),
    },
    "Standard View": {
        "direct": (
            "You are a legal document summarizer. Write a clear summary for a "
            "general audience. Cover the main terms, obligations, deadlines, and "
            "important conditions. Be concise and faithful to the text.\n\nTEXT:\n{text}\n\nSUMMARY:"
        ),
        "reduce": (
            "You are combining chunk summaries into one standard legal summary. "
            "Keep the answer concise, remove duplicates, preserve key obligations, "
            "rights, dates, fees, and page references.\n\nCHUNK SUMMARIES:\n{context}\n\nFINAL SUMMARY:"
        ),
    },
    "Detailed Breakdown": {
        "direct": (
            "You are a legal analyst. Provide a detailed but readable breakdown of "
            "the text. Organize by sections or issues, note important clauses, and "
            "include risks or obligations. Do not add outside legal knowledge.\n\nTEXT:\n{text}\n\nDETAILED BREAKDOWN:"
        ),
        "reduce": (
            "You are combining chunk summaries into a detailed legal analysis. "
            "Preserve section structure where possible, merge repeated points, and "
            "keep the result grounded in the provided summaries only.\n\nCHUNK SUMMARIES:\n{context}\n\nFINAL ANALYSIS:"
        ),
    },
}

QA_SYSTEM_PROMPT = (
    "You are a legal interview assistant. Answer only from the provided context. "
    "If the answer is not in the context, say exactly: information not found. "
    "Do not use outside knowledge. Be concise and cite page numbers when useful."
)

CHUNK_SUMMARY_PROMPT = (
    "Summarize this legal chunk for later merging. Keep it concise, factual, and "
    "grounded in the text only. Mention obligations, dates, money, rights, and any "
    "important clause language. Include the page number in your summary.\n\n"
    "PAGE: {page}\nCHUNK: {chunk_id}\nTEXT:\n{chunk_text}\n\nCHUNK SUMMARY:"
)

LLM_RERANK_PROMPT = (
    "You are a retrieval reranker for a legal QA system. Select the most relevant "
    "chunks for the user question. Return only a comma-separated list of candidate "
    "numbers in best-to-worst order. Do not explain. Do not add any extra text.\n\n"
    "QUESTION:\n{question}\n\nCANDIDATES:\n{candidates}\n\nORDER:"
)


def build_direct_summary_prompt(level: str, text: str) -> str:
    template = SUMMARY_LEVELS[level]["direct"]
    return template.format(text=text)


def build_reduce_summary_prompt(level: str, context: str) -> str:
    template = SUMMARY_LEVELS[level]["reduce"]
    return template.format(context=context)


def build_chunk_summary_prompt(page: int, chunk_id: str, chunk_text: str) -> str:
    return CHUNK_SUMMARY_PROMPT.format(page=page, chunk_id=chunk_id, chunk_text=chunk_text)


def build_rerank_prompt(question: str, candidates: str) -> str:
    return LLM_RERANK_PROMPT.format(question=question, candidates=candidates)
