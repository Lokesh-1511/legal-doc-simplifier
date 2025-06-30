# 🧾 Legal Document Simplifier + Chat Assistant

A powerful full-stack Python-based application that simplifies complex legal documents into easy-to-understand summaries using the LLaMA 3 model from Groq API. Users can upload legal PDFs or paste text, select the level of simplification, and interact with a chatbot to clarify their understanding.

---

## 🚀 Features

- ✅ **Upload PDFs** or paste legal text directly
- 🧠 **Choose simplification level**: ELI5, Standard View, or Detailed Breakdown
- 📄 **Automatic plain-English summaries**
- 💬 **Chat assistant** to answer user questions based on the simplified summary
- 🔐 **Environment-secured API key loading**

---

## 🛠️ Tech Stack

- `Python`
- `Gradio` – UI interface
- `PyMuPDF` – PDF text extraction
- `markdown` – Render Markdown to HTML
- `Groq API` – Powered by LLaMA 3 (70B)
- `dotenv` – Secure API key management

---

## 📦 Setup Instructions

### 1. Clone the Repository

```bash
git clone https://github.com/yourusername/legal-simplifier.git
cd legal-simplifier
