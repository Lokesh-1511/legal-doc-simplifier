# LegalEase - Lightweight Semantic Retrieval Upgrade

LegalEase is a practical student-friendly legal AI project built with FastAPI + HTML/CSS/JS.

This version upgrades chatbot behavior from:

- send full document to LLM

to:

- retrieve top relevant chunks using embeddings + cosine similarity
- send only retrieved context to Groq LLaMA3

The result is a lightweight RAG-style workflow without FAISS, vector DBs, Docker, or GPU dependencies.

## 🚀 Live Demo

Try the deployed version here: **[https://legal-ease15.vercel.app](https://legal-ease15.vercel.app)**

## What Changed

1. PDF extraction still uses PyMuPDF.
2. Text is split into overlapping chunks with page tracking.
3. Embeddings are generated using sentence-transformers (`all-MiniLM-L6-v2`).
4. Semantic retrieval uses `sklearn.metrics.pairwise.cosine_similarity`.
5. Chatbot prompts include only top-k retrieved chunks.
6. Responses include source attribution (`Page X`).

## Retrieval Pipeline (Simple RAG)

1. User uploads PDF or pastes text.
2. Backend extracts text (page-by-page for PDFs).
3. Chunking creates overlapping windows and stores:
   - `chunk_id`
   - `page`
   - `text`
4. Chunk embeddings are generated once and kept in memory.
5. For each user question:
   - Embed the query
   - Compute cosine similarity vs chunk embeddings
   - Select top-k chunks
   - Build retrieval-grounded prompt
   - Send to Groq LLaMA3
6. Return answer + `Source: Page X` information.

## Why This Is Lightweight

- No FAISS
- No ChromaDB
- No LangChain
- No Redis/pgvector
- No Docker
- No CUDA/GPU setup
- Works with in-memory Python objects and standard pip packages

## Tech Stack

- Python
- FastAPI
- PyMuPDF
- sentence-transformers
- scikit-learn
- Groq API (LLaMA3)
- HTML/CSS/JavaScript frontend

## Install (Windows Friendly)

```powershell
pip install -r requirements.txt
```

You can also install the two retrieval additions directly:

```powershell
pip install sentence-transformers scikit-learn
```

## Environment Setup

Create a `.env` file in project root:

```env
GROQ_API_KEY=your_groq_api_key_here
```

## Run

```powershell
.\server.ps1
```

Then open [web/index.html](web/index.html) in your browser.

## Key Backend Files

- [backend/main.py](backend/main.py): FastAPI routes, indexing lifecycle, retrieval-based prompting
- [backend/chunking.py](backend/chunking.py): overlapping chunk logic with page metadata
- [backend/retrieval.py](backend/retrieval.py): sentence-transformers embeddings + cosine similarity retrieval

## API Notes

### POST `/extract_pdf`

- Extracts PDF text page-by-page using PyMuPDF.
- Builds chunk index with real page numbers.

### POST `/simplify`

- Keeps document simplification flow.
- Ensures pasted text is also chunked/indexed for chat retrieval.

### POST `/chatbot`

Request example:

```json
{
  "summary": "...",
  "history": [],
  "question": "What are the termination conditions?",
  "top_k": 4
}
```

Response example:

```json
{
  "answer": "...",
  "sources": ["Source: Page 2", "Source: Page 3"]
}
```

## Prompt Guardrails

Chatbot instructions now enforce:

- answer only from retrieved context
- avoid hallucinations
- if context is insufficient, reply with: `information not found`

## Frontend Improvements

Kept the existing UI and added:

- chat loading state during retrieval + generation
- source chips under AI answers
- cleaner chat message rendering

## Project Structure

```text
legal-doc-simplifier/
├── backend/
│   ├── main.py
│   ├── chunking.py
│   └── retrieval.py
├── web/
│   ├── index.html
│   ├── script.js
│   └── style.css
├── requirements.txt
├── server.ps1
└── README.md
```
