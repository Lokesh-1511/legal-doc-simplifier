// Toggle input fields
const inputModeRadios = document.querySelectorAll('input[name="inputMode"]');
inputModeRadios.forEach(radio => {
  radio.addEventListener('change', function() {
    document.getElementById('pdfInput').style.display = this.value === 'Upload PDF' ? 'block' : 'none';
    document.getElementById('textInput').style.display = this.value === 'Paste Text' ? 'block' : 'none';
  });
});

// Simplify button click handler
const simplifyBtn = document.getElementById('simplifyBtn');
simplifyBtn.addEventListener('click', async function() {
  const inputMode = document.querySelector('input[name="inputMode"]:checked').value;
  const simplicity = document.querySelector('input[name="simplicity"]:checked').value;
  const output = document.getElementById('output');
  output.textContent = 'Processing...';

  let text = '';
  if (inputMode === 'Upload PDF') {
    const file = document.getElementById('pdfInput').files[0];
    if (!file) {
      output.textContent = '⚠️ Please upload a PDF file.';
      return;
    }
    // TODO: Add PDF extraction logic here (e.g., using PDF.js or send to backend)
    output.textContent = 'PDF extraction not implemented in frontend.';
    return;
  } else {
    text = document.getElementById('textInput').value.trim();
    if (!text) {
      output.textContent = '⚠️ Please paste some legal text.';
      return;
    }
  }

  // TODO: Replace with your API endpoint and key
  const apiUrl = 'YOUR_API_ENDPOINT';
  const apiKey = 'YOUR_API_KEY';

  try {
    const response = await fetch(apiUrl, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${apiKey}`,
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
    output.textContent = '⚠️ API Error: ' + err.message;
  }
});
