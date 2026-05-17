// Wait for DOM to be fully loaded
document.addEventListener('DOMContentLoaded', function() {

const API_BASE_URL = window.__API_BASE_URL || 'http://127.0.0.1:8000';

// --- Theme Toggle Logic ---
const themeToggle = document.getElementById('themeToggle');
const docElement = document.documentElement;

function setTheme(dark) {
  if (dark) {
    docElement.setAttribute('data-theme', 'dark');
    themeToggle.innerHTML = '<i class="fas fa-sun"></i>';
    localStorage.setItem('theme', 'dark');
  } else {
    docElement.setAttribute('data-theme', 'light');
    themeToggle.innerHTML = '<i class="fas fa-moon"></i>';
    localStorage.setItem('theme', 'light');
  }
}

themeToggle.addEventListener('click', () => {
  const isDark = docElement.getAttribute('data-theme') === 'dark';
  setTheme(!isDark);
});

// On load, set theme from localStorage or system preference
const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
const savedTheme = localStorage.getItem('theme');
setTheme(savedTheme === 'dark' || (!savedTheme && prefersDark));

// --- Input Method Toggle Logic ---
const tabButtons = document.querySelectorAll('.tab-btn');
const uploadZone = document.getElementById('uploadZone');
const textZone = document.getElementById('textZone');
const pdfInput = document.getElementById('pdfInput');
const textInput = document.getElementById('textInput');

tabButtons.forEach(btn => {
  btn.addEventListener('click', () => {
    // Remove active class from all tabs
    tabButtons.forEach(b => b.classList.remove('active'));
    // Add active class to clicked tab
    btn.classList.add('active');
    
    const method = btn.dataset.method;
    if (method === 'upload') {
      uploadZone.style.display = 'block';
      textZone.style.display = 'none';
    } else {
      uploadZone.style.display = 'none';
      textZone.style.display = 'block';
    }
  });
});

// Upload zone drag and drop functionality
uploadZone.addEventListener('click', () => {
  pdfInput.click();
});

uploadZone.addEventListener('dragover', (e) => {
  e.preventDefault();
  uploadZone.classList.add('dragover');
});

uploadZone.addEventListener('dragleave', () => {
  uploadZone.classList.remove('dragover');
});

uploadZone.addEventListener('drop', (e) => {
  e.preventDefault();
  uploadZone.classList.remove('dragover');
  const files = e.dataTransfer.files;
  if (files.length > 0 && files[0].type === 'application/pdf') {
    pdfInput.files = files;
    updateUploadUI(files[0]);
  }
});

pdfInput.addEventListener('change', (e) => {
  if (e.target.files.length > 0) {
    updateUploadUI(e.target.files[0]);
  }
});

function updateUploadUI(file) {
  const uploadContent = uploadZone.querySelector('.upload-content');
  uploadContent.innerHTML = `
    <i class="fas fa-file-pdf"></i>
    <h3>${file.name}</h3>
    <p>Click to choose a different file</p>
  `;
}

// --- Chatbot UI Logic ---
const chatWindow = document.getElementById('chatWindow');
const chatForm = document.getElementById('chatForm');
const chatInput = document.getElementById('chatInput');
const clearChatBtn = document.getElementById('clearChatBtn');
let chatHistory = [];
let loadingMessageEl = null;
let extractedPages = [];

function escapeHtml(text) {
  const map = {
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#039;'
  };
  return text.replace(/[&<>"']/g, (m) => map[m]);
}

function renderWelcomeMessage() {
    chatWindow.innerHTML = `
        <div class="welcome-message">
          <div class="ai-avatar">
            <i class="fas fa-robot"></i>
          </div>
          <div class="message-content">
            <p>Hello! I'm your AI legal assistant. Ask me anything about legal documents, terms, or concepts.</p>
          </div>
        </div>
    `;
}

clearChatBtn.addEventListener('click', () => {
    chatHistory = [];
    renderWelcomeMessage();
});

function appendMessage(role, text) {
  // Remove welcome message if it exists
  const welcomeMessage = chatWindow.querySelector('.welcome-message');
  if (welcomeMessage) {
    welcomeMessage.remove();
  }

  const msgDiv = document.createElement('div');
  msgDiv.className = `chat-message ${role}`;
  
  const avatar = document.createElement('div');
  avatar.className = role === 'user' ? 'user-avatar' : 'ai-avatar';
  avatar.innerHTML = role === 'user' ? '<i class="fas fa-user"></i>' : '<i class="fas fa-robot"></i>';
  
  const messageContent = document.createElement('div');
  messageContent.className = 'message-content';
  const textBlock = document.createElement('p');
  textBlock.className = 'chat-answer-text';
  textBlock.innerHTML = escapeHtml(text).replace(/\n/g, '<br>');
  messageContent.appendChild(textBlock);
  
  msgDiv.appendChild(avatar);
  msgDiv.appendChild(messageContent);
  chatWindow.appendChild(msgDiv);
  chatWindow.scrollTop = chatWindow.scrollHeight;
}

function appendAiMessageWithSources(text, sources = []) {
  appendMessage('ai', text);
  const lastMessage = chatWindow.lastElementChild;
  if (!lastMessage || !sources.length) {
    return;
  }

  const messageContent = lastMessage.querySelector('.message-content');
  const sourceBlock = document.createElement('div');
  sourceBlock.className = 'source-block';

  const sourceTitle = document.createElement('div');
  sourceTitle.className = 'source-title';
  sourceTitle.textContent = 'Sources';
  sourceBlock.appendChild(sourceTitle);

  const sourceList = document.createElement('div');
  sourceList.className = 'source-list';
  sources.forEach((source) => {
    const badge = document.createElement('span');
    badge.className = 'source-chip';
    badge.textContent = source;
    sourceList.appendChild(badge);
  });

  sourceBlock.appendChild(sourceList);
  messageContent.appendChild(sourceBlock);
}

function appendDebugBlock(debug) {
  if (!debug) return;

  const lastMessage = chatWindow.lastElementChild;
  if (!lastMessage) return;

  const messageContent = lastMessage.querySelector('.message-content');
  if (!messageContent) return;

  const debugBlock = document.createElement('details');
  debugBlock.className = 'debug-block';
  debugBlock.innerHTML = `
    <summary>Retrieval details</summary>
    <pre>${escapeHtml(JSON.stringify(debug, null, 2))}</pre>
  `;
  messageContent.appendChild(debugBlock);
}

function showChatLoading() {
  if (loadingMessageEl) {
    return;
  }

  loadingMessageEl = document.createElement('div');
  loadingMessageEl.className = 'chat-message ai loading-response';
  loadingMessageEl.innerHTML = `
    <div class="ai-avatar"><i class="fas fa-robot"></i></div>
    <div class="message-content">
      <p class="chat-answer-text"><i class="fas fa-spinner fa-spin"></i> Retrieving relevant chunks and preparing answer...</p>
    </div>
  `;
  chatWindow.appendChild(loadingMessageEl);
  chatWindow.scrollTop = chatWindow.scrollHeight;
}

function hideChatLoading() {
  if (loadingMessageEl) {
    loadingMessageEl.remove();
    loadingMessageEl = null;
  }
}

chatForm.addEventListener('submit', async function(e) {
  e.preventDefault();
  const userMsg = chatInput.value.trim();
  if (!userMsg) return;
  
  appendMessage('user', userMsg);
  chatInput.value = '';
  chatInput.disabled = true;
  const sendBtn = chatForm.querySelector('.send-btn');
  sendBtn.disabled = true;
  sendBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';
  showChatLoading();

  // Add to history
  chatHistory.push({role: 'user', content: userMsg});

  // Get simplified summary from output div
  const summary = document.getElementById('output').innerText.trim();
  if (!summary || summary === 'Your simplified document will appear here...') {
    hideChatLoading();
    appendMessage('ai', '⚠️ Please simplify a legal document first before asking questions.');
    chatInput.disabled = false;
    sendBtn.disabled = false;
    sendBtn.innerHTML = '<i class="fas fa-paper-plane"></i>';
    return;
  }

  // Prepare payload for backend
  const payload = {
    summary: summary,
    history: chatHistory.map(m => ({role: m.role, content: m.content})),
    question: userMsg,
    top_k: 4
  };

  try {
    const response = await fetch(`${API_BASE_URL}/chatbot`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(payload)
    });
    const data = await response.json();
    const aiMsg = data.answer || 'No answer returned.';
    hideChatLoading();
    appendAiMessageWithSources(aiMsg, data.sources || []);
    if (window.__SHOW_RETRIEVAL_DEBUG__ && data.debug) {
      appendDebugBlock(data.debug);
    }
    chatHistory.push({role: 'ai', content: aiMsg});
  } catch (err) {
    hideChatLoading();
    appendMessage('ai', '⚠️ API Error: ' + err.message);
  }
  
  chatInput.disabled = false;
  sendBtn.disabled = false;
  sendBtn.innerHTML = '<i class="fas fa-paper-plane"></i>';
});
// Simplify button click handler
const simplifyBtn = document.getElementById('simplifyBtn');
const output = document.getElementById('output');

// Initialize output with placeholder
output.innerHTML = '<p style="color: var(--text-secondary); font-style: italic;">Your simplified document will appear here...</p>';

simplifyBtn.addEventListener('click', async function() {
  const activeTab = document.querySelector('.tab-btn.active');
  const inputMethod = activeTab.dataset.method;
  const simplicity = document.querySelector('input[name="simplicity"]:checked').value;
  
  // Add loading state
  simplifyBtn.classList.add('loading');
  simplifyBtn.disabled = true;
  simplifyBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Processing...';
  
  output.innerHTML = '<div class="loading-message"><i class="fas fa-cog fa-spin"></i> Processing your document...</div>';

  let text = '';
  
  if (inputMethod === 'upload') {
    const file = pdfInput.files[0];
    if (!file) {
      resetSimplifyButton();
      output.innerHTML = '<p style="color: var(--error);">⚠️ Please upload a PDF file.</p>';
      return;
    }
    
    // Send PDF to backend for extraction
    const formData = new FormData();
    formData.append('file', file);
    
    try {
      const response = await fetch(`${API_BASE_URL}/extract_pdf`, {
        method: 'POST',
        body: formData
      });
      const data = await response.json();
      text = data.text;
      extractedPages = data.pages || [];
      if (!text || text.startsWith('⚠️')) {
        resetSimplifyButton();
        output.innerHTML = `<p style="color: var(--error);">${text || '⚠️ PDF extraction failed.'}</p>`;
        return;
      }
    } catch (err) {
      resetSimplifyButton();
      output.innerHTML = `<p style="color: var(--error);">⚠️ PDF extraction error: ${err.message}</p>`;
      return;
    }
  } else {
    text = textInput.value.trim();
    if (!text) {
      resetSimplifyButton();
      output.innerHTML = '<p style="color: var(--error);">⚠️ Please paste some legal text.</p>';
      return;
    }
  }

  // Send text and level to backend for simplification
  try {
    const response = await fetch(`${API_BASE_URL}/simplify`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        text: text,
        level: simplicity,
        pages: inputMethod === 'upload' ? extractedPages : []
      })
    });
    const data = await response.json();
    output.innerHTML = data.summary || 'No summary returned.';
    if (data.strategy) {
      const meta = document.createElement('div');
      meta.className = 'summary-meta';
      meta.textContent = `Strategy: ${data.strategy} | Estimated tokens: ${data.estimated_tokens || 'n/a'} | Chunks: ${data.chunk_count || 0}`;
      output.appendChild(meta);
    }
  } catch (err) {
    output.innerHTML = `<p style="color: var(--error);">⚠️ API Error: ${err.message}</p>`;
  }
  
  resetSimplifyButton();
});

function resetSimplifyButton() {
  simplifyBtn.classList.remove('loading');
  simplifyBtn.disabled = false;
  simplifyBtn.innerHTML = '<i class="fas fa-magic"></i> Simplify Document';
}

// Add copy to clipboard functionality
document.addEventListener('click', function(e) {
  if (e.target.closest('.icon-btn[title="Copy to clipboard"]')) {
    const content = output.innerText;
    if (content && content !== 'Your simplified document will appear here...') {
      navigator.clipboard.writeText(content).then(() => {
        const btn = e.target.closest('.icon-btn');
        const originalHTML = btn.innerHTML;
        btn.innerHTML = '<i class="fas fa-check"></i>';
        setTimeout(() => {
          btn.innerHTML = originalHTML;
        }, 2000);
      });
    }
  }
  
  if (e.target.closest('.icon-btn[title="Download as text"]')) {
    const content = output.innerText;
    if (content && content !== 'Your simplified document will appear here...') {
      const blob = new Blob([content], { type: 'text/plain' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'simplified-document.txt';
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    }
  }
});

}); // End of DOMContentLoaded
