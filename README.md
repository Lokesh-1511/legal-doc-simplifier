# 🧾 LegalEase - Legal Document Simplifier + Chat Assistant

A powerful full-stack web application that simplifies complex legal documents into easy-to-understand summaries using AI models from Groq API. Users can upload legal PDFs or paste text, select the level of simplification, and interact with a chatbot to clarify their understanding.

---

## 🚀 Features

- ✅ **Upload PDFs** or paste legal text directly
- 🧠 **Choose simplification level**: ELI5, Standard View, or Detailed Breakdown
- 📄 **Automatic plain-English summaries**
- 💬 **Interactive chat assistant** to answer user questions based on the simplified summary
- 🎨 **Modern responsive web interface** with dark/light theme toggle
- 🔐 **Environment-secured API key loading**
- ⚡ **Fast API backend** for optimal performance

---

## 🛠️ Tech Stack

### Backend
- `Python` – Core backend language
- `FastAPI` – Modern, fast web framework for building APIs
- `PyMuPDF` – PDF text extraction
- `markdown` – Render Markdown to HTML
- `Groq API` – Powered by AI models
- `dotenv` – Secure API key management

### Frontend
- `HTML5` – Semantic markup
- `CSS3` – Modern styling with responsive design
- `JavaScript` – Interactive frontend functionality
- `Font Awesome` – Icon library
- `Google Fonts` – Typography

---

## 📦 Setup Instructions

### 1. Clone the Repository

```bash
git clone https://github.com/yourusername/legal-doc-simplifier.git
cd legal-doc-simplifier
```

### 2. Install Python Dependencies

```bash
pip install -r requirements.txt
```

### 3. Environment Setup

Create a `.env` file in the project root:

```bash
GROQ_API_KEY=your_groq_api_key_here
```

### 4. Start the Backend Server

```bash
cd backend
python main.py
```
Or use the provided PowerShell script:
```powershell
.\server.ps1
```

### 5. Access the Application

Open your web browser and navigate to the frontend:
- Backend API: `http://localhost:8000`
- Frontend: Open `web/index.html` in your browser or serve it via a local server

---

## 📁 Project Structure

```
legal-doc-simplifier/
├── backend/
│   ├── main.py              # FastAPI backend server
│   └── __pycache__/
├── web/
│   ├── index.html           # Main frontend interface
│   ├── script.js            # Frontend JavaScript logic
│   ├── style.css            # Main stylesheet
│   └── style-new.css        # Additional styles
├── requirements.txt         # Python dependencies
├── server.ps1              # PowerShell server startup script
├── .env                    # Environment variables (create this)
└── README.md               # Project documentation
```

---

## 🔧 API Endpoints

### POST `/simplify`
Simplify legal document text
```json
{
  "text": "Legal document content...",
  "level": "Quick Summary (ELI5)" | "Standard View" | "Detailed Breakdown"
}
```

### POST `/extract_pdf`
Extract text from uploaded PDF
- Form data with PDF file

### POST `/chatbot`
Chat with AI assistant about the simplified document
```json
{
  "summary": "Simplified document summary...",
  "history": [...],
  "question": "User question about the document"
}
```

---

## 🚀 Usage

1. **Upload Document**: Choose to upload a PDF file or paste legal text directly
2. **Select Simplification Level**: 
   - **ELI5**: Simple, easy-to-understand explanation
   - **Standard View**: Clear summary for general audience
   - **Detailed Breakdown**: Comprehensive analysis with key sections
3. **Get Summary**: AI processes your document and provides a simplified version
4. **Ask Questions**: Use the chat assistant to clarify any points about your document

---

## 🔐 Security Notes

- Keep your `.env` file secure and never commit it to version control
- Your API keys are loaded securely through environment variables
- The application uses CORS middleware for secure cross-origin requests

---

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

---

## 📄 License

This project is licensed under the MIT License.
