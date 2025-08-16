from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import fitz  # PyMuPDF
import os
from groq import Groq
from dotenv import load_dotenv, find_dotenv
from markdown import markdown

# Try loading .env from backend folder, then from project root
env_loaded = load_dotenv(find_dotenv())
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
if not GROQ_API_KEY:
    print("WARNING: GROQ_API_KEY not found. Ensure .env is in backend or project root and contains GROQ_API_KEY=your_actual_key_here")
else:
    print("GROQ_API_KEY loaded successfully.")
MODEL_NAME = "openai/gpt-oss-20b"
client = Groq(api_key=GROQ_API_KEY)
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

@app.post("/simplify")
def simplify(req: SimplifyRequest):
    prompt = PROMPTS[req.level].format(text=req.text)
    try:
        completion = client.chat.completions.create(
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
    try:
        with fitz.open(stream=file.file.read(), filetype="pdf") as doc:
            text = "\n".join([page.get_text() for page in doc])
        return {"text": text}
    except Exception as e:
        return {"text": f"⚠️ PDF Error: {e}"}

@app.post("/chatbot")
def chatbot(req: ChatbotRequest):
    system_prompt = f"""
    You are a helpful legal assistant. A user has received a simplified summary of a legal document.
    Your job is to answer their questions based ONLY on the provided summary.
    Be friendly, clear, and concise.

    Summary:
    ---
    {req.summary}
    ---
    Now answer the question.
    """
    messages = [{"role": "system", "content": system_prompt}]
    for m in req.history:
        if m["role"] == "user":
            messages.append({"role": "user", "content": m["content"]})
        elif m["role"] == "ai":
            messages.append({"role": "assistant", "content": m["content"]})
    messages.append({"role": "user", "content": req.question})
    try:
        completion = client.chat.completions.create(
            model=MODEL_NAME,
            messages=messages,
            temperature=0.5,
            max_tokens=1000
        )
        answer = completion.choices[0].message.content.strip()
        return {"answer": answer}
    except Exception as e:
        return {"answer": f"⚠️ API Error: {e}"}
