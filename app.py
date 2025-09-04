import gradio as gr
import requests
import json
import fitz  # PyMuPDF
from markdown import markdown
import os
from dotenv import load_dotenv

# --- Load environment variables from .env ---
load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# --- Configuration ---
API_URL = "https://api.groq.com/openai/v1/chat/completions"
HEADERS = {
    "Authorization": f"Bearer {GROQ_API_KEY}",
    "Content-Type": "application/json"
}
MODEL_NAME = "llama3-70b-8192"

# --- Global Storage ---
stored_legal_text = ""
simplified_summary = ""

# --- Prompts for Different Simplification Levels ---
PROMPTS = {
    "Quick Summary (ELI5)": """You are an expert legal analyst who can explain complex legal documents to a five-year-old. Your goal is to provide a super simple, easy-to-understand summary. Use short sentences, simple words, and analogies a child can grasp. Do not include any legal jargon. Focus on the main points: Who is involved? What is the main purpose of the document? What are the most important things someone needs to know?

Here is the legal text:
---
{text}
---

Provide the ELI5 summary below:""",
    "Standard View": """You are a professional legal assistant. Your task is to simplify a complex legal document into a clear and concise summary for a layperson. Your summary should be well-structured, using headings, bullet points, and bold text to highlight key information. Avoid legal jargon where possible, but if you must use a legal term, explain it simply. The goal is to make the document accessible and understandable without losing critical information.

Here is the legal text:
---
{text}
---

Provide the simplified 'Standard View' summary below:""",
    "Detailed Breakdown": """You are a meticulous legal analyst. Your job is to provide a detailed, section-by-section breakdown of a legal document. For each major clause or section, you must:
1.  Provide the original section title or a clear heading.
2.  Summarize the key points of that section in clear, easy-to-understand language.
3.  Identify and explain any potential risks, obligations, or important deadlines for the user.
4.  Use formatting (like nested bullet points and bold text) to create a highly organized and readable structure.

Here is the legal text:
---
{text}
---

Provide the 'Detailed Breakdown' below:"""
}

# Simplify logic
def simplify_text(text, level):
    """Calls the Groq API to simplify the text based on the selected level."""
    global simplified_summary
    if not GROQ_API_KEY:
        return "⚠️ **API Key Missing!** Please set your `GROQ_API_KEY` in a `.env` file."
    prompt = PROMPTS[level].format(text=text)
    payload = {
        "model": MODEL_NAME,
        "messages": [
            {"role": "system", "content": "You are a world-class legal document simplifier. You follow instructions precisely."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.2, "max_tokens": 2000
    }
    try:
        response = requests.post(API_URL, headers=HEADERS, data=json.dumps(payload))
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        return f"⚠️ API Error: {e}"
    raw_output = response.json()["choices"][0]["message"]["content"].strip()
    simplified_summary = raw_output
    return markdown(raw_output)

# PDF extraction
def extract_text_from_pdf(file_obj):
    """Extracts text from an uploaded PDF file."""
    try:
        with fitz.open(stream=file_obj.read(), filetype="pdf") as doc:
            return "\n".join([page.get_text() for page in doc])
    except Exception as e:
        return f"⚠️ PDF Error: {e}"

# Input handler
def handle_input(input_mode, file_input, text_input, simplicity_level, progress=gr.Progress()):
    """Handles the user input from the Gradio interface and calls the simplifier."""
    global stored_legal_text, simplified_summary
    simplified_summary = ""
    text = ""
    progress(0, desc="Starting...")

    if input_mode == "Upload PDF":
        if file_input is None: return "⚠️ Please upload a PDF file.", ""
        progress(0.2, desc="Extracting text from PDF...")
        text = extract_text_from_pdf(file_input)
    elif input_mode == "Paste Text":
        if not text_input.strip(): return "⚠️ Please paste some legal text.", ""
        text = text_input
    else:
        return "⚠️ Invalid input mode selected.", ""

    if "⚠️" in text or not text.strip():
        return text, "" # Return error if extraction failed or no text found

    stored_legal_text = text.strip()
    progress(0.5, desc="Simplifying document...")
    simplified_html = simplify_text(stored_legal_text, simplicity_level)
    progress(1, desc="Done!")

    # Clear chat history and provide a welcome message
    welcome_message = "Summary complete! Feel free to ask me any questions about it."
    return simplified_html, [[None, welcome_message]]

# Chatbot function
def legal_chatbot(user_input, history):
    """Handles the chat interaction based on the simplified summary."""
    global simplified_summary
    if not simplified_summary.strip():
        return "⚠️ Please simplify a legal document first before asking questions."
    system_prompt = f"""
    You are a helpful legal assistant. A user has received a simplified summary of a legal document.
    Your job is to answer their questions based ONLY on the provided summary.
    Do not invent information or use external knowledge. If the answer is not in the summary, say so.
    Be friendly, clear, and concise.

    Provided Summary:
    ---
    {simplified_summary}
    ---
    Now, answer the user's question.
    """
    messages = [{"role": "system", "content": system_prompt}]
    # Add previous conversation history
    for user_msg, assistant_msg in history[:-1]: # Exclude the latest user_input
        if user_msg: messages.append({"role": "user", "content": user_msg})
        if assistant_msg: messages.append({"role": "assistant", "content": assistant_msg})

    messages.append({"role": "user", "content": user_input})

    payload = {
        "model": MODEL_NAME,
        "messages": messages,
        "temperature": 0.5,
        "max_tokens": 1000
    }
    try:
        response = requests.post(API_URL, headers=HEADERS, data=json.dumps(payload))
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"].strip()
    except requests.exceptions.RequestException as e:
        return f"⚠️ API Error: {e}"

# 🌐 Gradio UI
def create_ui():
    """Creates and returns the Gradio UI Blocks."""
    with gr.Blocks(theme=gr.themes.Soft(), css="#disclaimer {color: grey; font-size: 0.9em;}") as demo:
        gr.Markdown("## Legal Document Simplifier + Chat Assistant")
        with gr.Row():
            with gr.Column(scale=2):
                gr.Markdown("### 1. Provide Your Document")
                input_mode = gr.Radio(["Upload PDF", "Paste Text"], label="Input Method", value="Upload PDF")
                pdf_input = gr.File(label="Upload PDF File", file_types=[".pdf"], visible=True)
                text_input = gr.Textbox(label="Paste Legal Text Here", lines=15, visible=False)
                
                input_mode.change(
                    lambda mode: (gr.update(visible=mode == "Upload PDF"), gr.update(visible=mode == "Paste Text")),
                    inputs=input_mode,
                    outputs=[pdf_input, text_input]
                )
                
                gr.Markdown("### 2. Choose Simplification Level")
                simplicity_level = gr.Radio(
                    ["Quick Summary (ELI5)", "Standard View", "Detailed Breakdown"],
                    label="Simplification Level",
                    value="Standard View"
                )
                
                simplify_btn = gr.Button("Simplify Document", variant="primary")
                
                gr.Markdown("### 3. Get Your Simplified Summary")
                simplified_output = gr.HTML(label="Simplified Document")

            with gr.Column(scale=1):
                gr.Markdown("### 4. Ask Questions")
                chatbot = gr.Chatbot(label="AI Legal Assistant", bubble_full_width=False, height=500)
                chat_interface = gr.ChatInterface(
                    fn=legal_chatbot,
                    chatbot=chatbot,
                    examples=[
                        "What is the main purpose of this document?",
                        "Who are the parties involved?",
                        "Are there any important dates I should be aware of?"
                    ],
                    title=None # Hide the default title
                )

        simplify_btn.click(
            fn=handle_input,
            inputs=[input_mode, pdf_input, text_input, simplicity_level],
            outputs=[simplified_output, chatbot]
        )
        gr.Markdown("_Disclaimer: This tool is for informational purposes only and does not constitute legal advice._", elem_id="disclaimer")
    return demo

if __name__ == "__main__":
    app = create_ui()
    app.launch(debug=True, share=True)
