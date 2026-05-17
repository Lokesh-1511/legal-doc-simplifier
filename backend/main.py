from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import fitz  # PyMuPDF
import os
from typing import List, Optional
from groq import Groq
from dotenv import load_dotenv, find_dotenv
from markdown import markdown
try:
    from .chunking import chunk_pages, chunk_plain_text
    from .retrieval import SemanticRetriever
    from .summarizer import DocumentSummarizer
    from .reranker import format_context_block, llm_rerank_chunks, source_pages_label
    from .prompts import QA_SYSTEM_PROMPT
except ImportError:
    from chunking import chunk_pages, chunk_plain_text
    from retrieval import SemanticRetriever
    from summarizer import DocumentSummarizer
    from reranker import format_context_block, llm_rerank_chunks, source_pages_label
    from prompts import QA_SYSTEM_PROMPT

# Load environment variables
env_loaded = load_dotenv(find_dotenv())
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
HF_API_TOKEN = os.getenv("HF_API_TOKEN")

if not GROQ_API_KEY:
    print("⚠️  WARNING: GROQ_API_KEY not found. Simplification and chatbot will not work.")
else:
    print("✓ GROQ_API_KEY loaded successfully.")

if not HF_API_TOKEN:
    print("⚠️  WARNING: HF_API_TOKEN not found. Semantic retrieval will not work.")
    print("   Get a free token at: https://huggingface.co/settings/tokens")
else:
    print("✓ HF_API_TOKEN loaded successfully.")

MODEL_NAME = "llama-3.3-70b-versatile"
client: Optional[Groq] = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None
retriever = SemanticRetriever()
summarizer = DocumentSummarizer()
chunk_store: List[dict] = []
stored_document_text = ""
stored_document_pages: List[dict] = []
last_extracted_pdf_text = ""

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class SimplifyRequest(BaseModel):
    text: str
    level: str
    pages: Optional[List[dict]] = None

class ChatbotRequest(BaseModel):
    summary: str
    history: list
    question: str
    top_k: int = 4


def extract_pages_from_pdf(file_bytes: bytes) -> List[dict]:
    pages: List[dict] = []
    with fitz.open(stream=file_bytes, filetype="pdf") as doc:
        for index, page in enumerate(doc, start=1):
            pages.append({"page": index, "text": page.get_text()})
    return pages


def rebuild_index_from_chunks(chunks: List[dict]) -> None:
    global chunk_store
    chunk_store = chunks
    retriever.build_index(chunk_store)


def rebuild_index_from_text(text: str) -> None:
    chunks = chunk_plain_text(text)
    rebuild_index_from_chunks(chunks)


def get_groq_client() -> Optional[Groq]:
    return client


@app.post("/simplify")
def simplify(req: SimplifyRequest):
    global stored_document_text, stored_document_pages
    stored_document_text = req.text.strip()
    stored_document_pages = req.pages or []

    groq_client = get_groq_client()
    if groq_client is None:
        return {"summary": "⚠️ GROQ_API_KEY is missing. Add it to .env to enable simplification."}

    try:
        if stored_document_pages:
            rebuild_index_from_chunks(chunk_pages(stored_document_pages))
        elif stored_document_text and (not chunk_store or stored_document_text != last_extracted_pdf_text):
            rebuild_index_from_text(stored_document_text)

        result = summarizer.summarize(
            text=req.text,
            level=req.level,
            groq_client=groq_client,
            pages=req.pages,
            model_name=MODEL_NAME,
        )
        return {
            "summary": markdown(result.summary),
            "strategy": result.strategy,
            "estimated_tokens": result.estimated_tokens,
            "chunk_count": result.chunk_count,
            "chunk_summaries": result.chunk_summaries,
        }
    except Exception as e:
        return {"summary": f"⚠️ API Error: {e}"}

@app.post("/extract_pdf")
def extract_pdf(file: UploadFile = File(...)):
    global last_extracted_pdf_text, stored_document_pages, stored_document_text
    try:
        file_bytes = file.file.read()
        pages = extract_pages_from_pdf(file_bytes)
        text = "\n".join([str(page["text"]) for page in pages])
        rebuild_index_from_chunks(chunk_pages(pages))
        stored_document_pages = pages
        stored_document_text = text.strip()
        last_extracted_pdf_text = text.strip()
        return {"text": text, "pages": pages, "page_count": len(pages), "chunk_count": len(chunk_store)}
    except Exception as e:
        return {"text": f"⚠️ PDF Error: {e}"}

@app.post("/chatbot")
def chatbot(req: ChatbotRequest):
    """
    Legal assistant chatbot powered by semantic retrieval + LLM.
    
    Flow:
    1. Retrieve semantically similar chunks from uploaded document
    2. Inject into LLM system prompt as context
    3. LLM answers question using only provided context
    
    This prevents hallucination (making up legal information).
    If no relevant context found, LLM returns "information not found".
    """
    if not HF_API_TOKEN:
        return {
            "answer": "⚠️ HF_API_TOKEN is missing. Add it to .env to enable semantic retrieval. Get a free token at https://huggingface.co/settings/tokens",
            "sources": [],
        }
    
    if not chunk_store:
        return {
            "answer": "⚠️ Please upload or paste a document first so I can retrieve relevant context.",
            "sources": [],
        }

    top_k = max(3, min(req.top_k, 5))

    doc_token_estimate = summarizer.estimate_tokens(stored_document_text or req.summary or "")
    small_document = doc_token_estimate <= summarizer.direct_token_limit or len(chunk_store) <= 3

    if small_document:
        print(f"📄 Small document QA path (~{doc_token_estimate} tokens). Using full context.")
        candidate_chunks = chunk_store[:]
        rerank_meta = {"mode": "full_context"}
        selected_chunks = candidate_chunks
    else:
        print(f"📚 Large document QA path (~{doc_token_estimate} tokens). Using retrieval + reranking.")
        candidate_chunks = retriever.search(req.question, top_k=5, min_similarity=0.25)
        if not candidate_chunks:
            return {
                "answer": "❌ Could not find relevant information in the document. Try rephrasing the question or asking about a more specific clause.",
                "sources": [],
            }

        selected_chunks, rerank_meta = llm_rerank_chunks(
            question=req.question,
            candidates=candidate_chunks,
            groq_client=get_groq_client(),
            model_name=MODEL_NAME,
            max_selected=top_k,
        )
        if not selected_chunks:
            selected_chunks = candidate_chunks[:top_k]

    context_block = format_context_block(selected_chunks)
    source_label = source_pages_label(selected_chunks)

    messages = [{"role": "system", "content": QA_SYSTEM_PROMPT}]
    
    # Add conversation history for context awareness
    for m in req.history:
        if m["role"] == "user":
            messages.append({"role": "user", "content": m["content"]})
        elif m["role"] == "ai":
            messages.append({"role": "assistant", "content": m["content"]})

    # Build retrieval-augmented prompt with clear context boundaries
    retrieval_prompt = f"""CONTEXT:
---
{context_block}
---

QUESTION:
{req.question}

Remember: answer only from the context above. If the answer is not present, say "information not found"."""
    
    messages.append({"role": "user", "content": retrieval_prompt})

    groq_client = get_groq_client()
    if groq_client is None:
        return {
            "answer": "⚠️ GROQ_API_KEY is missing. Add it to .env to enable chatbot responses.",
            "sources": [source_label],
        }

    try:
        completion = groq_client.chat.completions.create(
            model=MODEL_NAME,
            messages=messages,
            temperature=0.5,  # Balanced: some creativity but grounded
            max_tokens=1000
        )
        answer = completion.choices[0].message.content.strip()
        return {
            "answer": answer,
            "sources": [source_label],
            "debug": {
                "mode": rerank_meta.get("mode", "unknown"),
                "candidate_count": len(candidate_chunks),
                "selected_count": len(selected_chunks),
                "document_tokens": doc_token_estimate,
            },
        }
    except Exception as e:
        return {"answer": f"⚠️ API Error: {e}", "sources": [source_label]}
