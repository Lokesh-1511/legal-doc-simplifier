// Wait for DOM to be fully loaded
document.addEventListener('DOMContentLoaded', function() {

// --- Theme Toggle Logic ---
const themeToggle = document.getElementById('themeToggle');
const body = document.body;

function setTheme(dark) {
  if (dark) {
    body.classList.add('dark');
    themeToggle.innerHTML = '<i class="fas fa-sun"></i>';
    localStorage.setItem('theme', 'dark');
  } else {
    body.classList.remove('dark');
    themeToggle.innerHTML = '<i class="fas fa-moon"></i>';
    localStorage.setItem('theme', 'light');
  }
}

themeToggle.addEventListener('click', () => {
  setTheme(!body.classList.contains('dark'));
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
let chatHistory = [];

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
  messageContent.innerHTML = text;
  
  msgDiv.appendChild(avatar);
  msgDiv.appendChild(messageContent);
  chatWindow.appendChild(msgDiv);
  chatWindow.scrollTop = chatWindow.scrollHeight;
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

  // Add to history
  chatHistory.push({role: 'user', content: userMsg});

  // Get simplified summary from output div
  const summary = document.getElementById('output').innerText.trim();
  if (!summary || summary === 'Your simplified document will appear here...') {
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
    question: userMsg
  };

  try {
    const response = await fetch('http://127.0.0.1:8000/chatbot', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(payload)
    });
    const data = await response.json();
    const aiMsg = data.answer || 'No answer returned.';
    appendMessage('ai', aiMsg);
    chatHistory.push({role: 'ai', content: aiMsg});
  } catch (err) {
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
      const response = await fetch('http://127.0.0.1:8000/extract_pdf', {
        method: 'POST',
        body: formData
      });
      const data = await response.json();
      text = data.text;
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
    const response = await fetch('http://127.0.0.1:8000/simplify', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        text: text,
        level: simplicity
      })
    });
    const data = await response.json();
    output.innerHTML = data.summary || 'No summary returned.';
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
