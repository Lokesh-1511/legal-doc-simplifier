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
except ImportError:
    from chunking import chunk_pages, chunk_plain_text
    from retrieval import SemanticRetriever

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
chunk_store: List[dict] = []
stored_document_text = ""
last_extracted_pdf_text = ""
PROMPTS = {
    "Quick Summary (ELI5)": "You are a world-class legal document simplifier. Your job is to read the following legal text and provide a quick summary in simple language (ELI5 - Explain Like I'm 5). Focus on the main points, avoid jargon, and make it easy for anyone to understand.\n\nLegal Text:\n{text}\n\nSummary:",
    "Standard View": "You are a world-class legal document simplifier. Your job is to read the following legal text and provide a clear, concise summary for a general audience. Highlight the key points, obligations, and rights.\n\nLegal Text:\n{text}\n\nSummary:",
    "Detailed Breakdown": "You are a world-class legal document simplifier. Your job is to read the following legal text and provide a detailed breakdown. List the main sections, summarize each, and explain any important terms or clauses.\n\nLegal Text:\n{text}\n\nDetailed Breakdown:"
}

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
    global stored_document_text
    stored_document_text = req.text.strip()

    # Preserve PDF page-aware chunks created by /extract_pdf.
    should_reindex_plain_text = (
        stored_document_text
        and (not chunk_store or stored_document_text != last_extracted_pdf_text)
    )
    if should_reindex_plain_text:
        rebuild_index_from_text(stored_document_text)

    prompt = PROMPTS[req.level].format(text=req.text)
    groq_client = get_groq_client()
    if groq_client is None:
        return {"summary": "⚠️ GROQ_API_KEY is missing. Add it to .env to enable simplification."}

    try:
        completion = groq_client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": "You are a world-class legal document simplifier. You follow instructions precisely."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2,
            max_tokens=2000
        )
        raw_output = completion.choices[0].message.content.strip()
        return {"summary": markdown(raw_output)}
    except Exception as e:
        return {"summary": f"⚠️ API Error: {e}"}

@app.post("/extract_pdf")
def extract_pdf(file: UploadFile = File(...)):
    global last_extracted_pdf_text
    try:
        file_bytes = file.file.read()
        pages = extract_pages_from_pdf(file_bytes)
        text = "\n".join([str(page["text"]) for page in pages])
        rebuild_index_from_chunks(chunk_pages(pages))
        last_extracted_pdf_text = text.strip()
        return {"text": text}
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
    from .retrieval_helpers import format_context_block
    
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

    top_k = max(1, min(req.top_k, 8))
    
    # Retrieve chunks using semantic similarity (embeddings + keyword re-ranking)
    retrieved_chunks = retriever.search(req.question, top_k=top_k, min_similarity=0.3)
    
    # Fallback: if no chunks found, return helpful error
    if not retrieved_chunks:
        return {
            "answer": "❌ Could not find relevant information in the document. Try:\n- Using more descriptive language\n- Breaking complex questions into simpler parts\n- Asking about specific document sections",
            "sources": [],
        }
    
    # Format context with improved layout
    context_block = format_context_block(retrieved_chunks)
    source_pages = sorted({int(chunk["page"]) for chunk in retrieved_chunks})

    # System prompt enforces context-only answering (prevents hallucination)
    system_prompt = """You are a legal interview preparation assistant.

CRITICAL RULES:
1. Answer ONLY using the retrieved context below
2. If the context doesn't contain the answer, respond exactly: "information not found"
3. Do NOT use external legal knowledge or hallucinate
4. Be concise and student-friendly
5. Cite the page number when relevant

Your role: Help students understand actual document clauses, not teach general law."""

    messages = [{"role": "system", "content": system_prompt}]
    
    # Add conversation history for context awareness
    for m in req.history:
        if m["role"] == "user":
            messages.append({"role": "user", "content": m["content"]})
        elif m["role"] == "ai":
            messages.append({"role": "assistant", "content": m["content"]})

    # Build retrieval-augmented prompt with clear context boundaries
    retrieval_prompt = f"""RETRIEVED CONTEXT:
---
{context_block}
---

USER QUESTION:
{req.question}

Remember: Answer ONLY from the context above. If not found, say "information not found"."""
    
    messages.append({"role": "user", "content": retrieval_prompt})

    groq_client = get_groq_client()
    if groq_client is None:
        return {
            "answer": "⚠️ GROQ_API_KEY is missing. Add it to .env to enable chatbot responses.",
            "sources": [f"Source: Page {page}" for page in source_pages],
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
            "sources": [f"Source: Page {page}" for page in source_pages],
        }
    except Exception as e:
        return {"answer": f"⚠️ API Error: {e}", "sources": []}
