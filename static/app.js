const chat = document.getElementById('chat');
const input = document.getElementById('input');
const btnSend = document.getElementById('btn-send');
const btnIndex = document.getElementById('btn-index');
const btnClear = document.getElementById('btn-clear');
const docCount = document.getElementById('doc-count');
const dialog = document.getElementById('index-dialog');
const idxInput = document.getElementById('idx-input');

// Auto-resize textarea
input.addEventListener('input', () => {
    input.style.height = 'auto';
    input.style.height = Math.min(input.scrollHeight, 150) + 'px';
});

// Send on Enter (shift+enter for newline)
input.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
    }
});

btnSend.addEventListener('click', sendMessage);

// Index dialog
btnIndex.addEventListener('click', () => dialog.showModal());
document.getElementById('idx-cancel').addEventListener('click', () => dialog.close());

document.querySelectorAll('input[name="idx-type"]').forEach(radio => {
    radio.addEventListener('change', () => {
        const placeholders = {
            github: 'owner/repo (e.g. amastbau/hybrid-llm)',
            dir: '/path/to/directory',
            crawl: 'https://example.com/docs',
        };
        idxInput.placeholder = placeholders[radio.value] || '';
    });
});

document.getElementById('idx-go').addEventListener('click', async () => {
    const type = document.querySelector('input[name="idx-type"]:checked').value;
    const value = idxInput.value.trim();
    if (!value) return;

    dialog.close();
    addMessage('user', `Indexing ${type}: ${value}...`);

    const endpoints = {
        github: '/api/index/github',
        dir: '/api/index/directory',
        crawl: '/api/index/crawl',
    };
    const bodies = {
        github: { repo: value },
        dir: { path: value },
        crawl: { url: value },
    };
    const endpoint = endpoints[type];
    const body = bodies[type];

    try {
        const res = await fetch(endpoint, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body),
        });
        const data = await res.json();
        if (data.error) {
            addMessage('assistant', `Error: ${data.error}`, true);
        } else {
            addMessage('assistant', `Indexed ${data.indexed} documents.`);
        }
    } catch (e) {
        addMessage('assistant', `Error: ${e.message}`, true);
    }
    refreshStats();
    idxInput.value = '';
});

// Clear
btnClear.addEventListener('click', async () => {
    if (!confirm('Clear all indexed documents?')) return;
    await fetch('/api/clear', { method: 'POST' });
    chat.innerHTML = '';
    refreshStats();
});

// Stats
async function refreshStats() {
    try {
        const res = await fetch('/api/stats');
        const data = await res.json();
        docCount.textContent = data.documents;
    } catch {
        docCount.textContent = '?';
    }
}

// Add a message to the chat
function addMessage(role, content, isError = false) {
    const div = document.createElement('div');
    div.className = `message ${role}`;
    if (isError) {
        div.innerHTML = `<div class="error">${escapeHtml(content)}</div>`;
    } else if (role === 'assistant') {
        div.innerHTML = `<div class="content">${marked.parse(content)}</div>`;
    } else {
        div.textContent = content;
    }
    chat.appendChild(div);
    chat.scrollTop = chat.scrollHeight;
    return div;
}

function escapeHtml(text) {
    const d = document.createElement('div');
    d.textContent = text;
    return d.innerHTML;
}

// Send message with streaming
async function sendMessage() {
    const text = input.value.trim();
    if (!text) return;

    input.value = '';
    input.style.height = 'auto';
    btnSend.disabled = true;

    addMessage('user', text);

    // Create assistant message container
    const assistantDiv = document.createElement('div');
    assistantDiv.className = 'message assistant';
    const contentDiv = document.createElement('div');
    contentDiv.className = 'content';
    contentDiv.innerHTML = '<span class="typing">...</span>';
    assistantDiv.appendChild(contentDiv);
    chat.appendChild(assistantDiv);
    chat.scrollTop = chat.scrollHeight;

    let fullContent = '';
    let sources = [];

    try {
        const res = await fetch('/api/chat/stream', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: text }),
        });

        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n');
            buffer = lines.pop();

            for (const line of lines) {
                if (!line.startsWith('data: ')) continue;
                const data = JSON.parse(line.slice(6));

                if (data.type === 'content') {
                    fullContent += data.content;
                    contentDiv.innerHTML = marked.parse(fullContent);
                    chat.scrollTop = chat.scrollHeight;
                } else if (data.type === 'sources') {
                    sources = data.sources;
                } else if (data.type === 'error') {
                    contentDiv.innerHTML = `<div class="error">${escapeHtml(data.error)}</div>`;
                } else if (data.type === 'rag_error') {
                    // RAG error is non-fatal, continue
                }
            }
        }

        // Add sources
        if (sources.length > 0) {
            const srcDiv = document.createElement('div');
            srcDiv.className = 'sources';
            srcDiv.innerHTML = '<strong>Sources:</strong> ' + sources.map(s => {
                const url = s.url || s.doc_id;
                if (url.startsWith('http')) {
                    return `<a href="${url}" target="_blank">${s.doc_id}</a>`;
                }
                return `<span>${url}</span>`;
            }).join(', ');
            assistantDiv.appendChild(srcDiv);
        }

    } catch (e) {
        contentDiv.innerHTML = `<div class="error">Connection error: ${escapeHtml(e.message)}</div>`;
    }

    btnSend.disabled = false;
    input.focus();
}

// Init
refreshStats();
input.focus();
