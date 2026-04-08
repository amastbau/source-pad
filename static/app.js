const chat = document.getElementById('chat');
const input = document.getElementById('input');
const btnSend = document.getElementById('btn-send');
const btnIndex = document.getElementById('btn-index');
const btnClear = document.getElementById('btn-clear');
const btnToggleTrace = document.getElementById('btn-toggle-trace');
const docCount = document.getElementById('doc-count');
const dialog = document.getElementById('index-dialog');
const idxInput = document.getElementById('idx-input');
const tracePanel = document.getElementById('trace-panel');
const traceContent = document.getElementById('trace-content');

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

// Trace panel toggle
btnToggleTrace.addEventListener('click', () => {
    tracePanel.classList.toggle('hidden');
    btnToggleTrace.classList.toggle('active');
});

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

// Clear trace
document.getElementById('btn-clear-trace').addEventListener('click', clearTrace);

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

// === Trace panel functions ===

function clearTrace() {
    traceContent.innerHTML = '<div class="trace-status" id="trace-status">Waiting for query...</div>';
}

function setTraceStatus(text, active = false) {
    const el = document.getElementById('trace-status');
    if (el) {
        el.textContent = text;
        el.className = 'trace-status' + (active ? ' active' : '');
    }
}

function addTraceSection(type, title, data) {
    // Remove "waiting" status
    const status = document.getElementById('trace-status');
    if (status && status.textContent === 'Waiting for query...') {
        status.remove();
    }

    const id = 'ts-' + Date.now() + Math.random().toString(36).slice(2, 5);
    const section = document.createElement('div');
    section.className = 'trace-section';
    section.id = id;

    let bodyHtml = '';
    if (typeof data === 'object' && data !== null) {
        bodyHtml = formatTraceData(data);
    } else {
        bodyHtml = `<pre>${escapeHtml(String(data))}</pre>`;
    }

    section.innerHTML = `
        <div class="trace-section-header ${type}" onclick="toggleTrace('${id}')">
            <span>${title}</span>
            <span class="trace-toggle">&#9660;</span>
        </div>
        <div class="trace-section-body">${bodyHtml}</div>
    `;

    traceContent.appendChild(section);
    traceContent.scrollTop = traceContent.scrollHeight;
}

function formatTraceData(data) {
    let html = '';
    for (const [key, value] of Object.entries(data)) {
        if (key === 'messages' && Array.isArray(value)) {
            html += `<div class="trace-key">messages (${value.length}):</div>`;
            for (const msg of value) {
                html += `<div class="trace-msg-role">${escapeHtml(msg.role || '?')} (${msg.content_length || '?'} chars)</div>`;
                if (msg.preview) {
                    html += `<div class="trace-msg-preview">${escapeHtml(msg.preview)}</div>`;
                }
            }
        } else if (Array.isArray(value)) {
            html += `<div class="trace-key">${escapeHtml(key)}:</div>`;
            for (const item of value) {
                html += `<pre>  ${escapeHtml(String(item))}</pre>`;
            }
        } else if (typeof value === 'object' && value !== null) {
            html += `<div class="trace-key">${escapeHtml(key)}:</div>`;
            html += `<pre>${escapeHtml(JSON.stringify(value, null, 2))}</pre>`;
        } else {
            html += `<div><span class="trace-key">${escapeHtml(key)}:</span><span class="trace-value">${escapeHtml(String(value))}</span></div>`;
        }
    }
    return html;
}

window.toggleTrace = function(id) {
    const section = document.getElementById(id);
    if (!section) return;
    const body = section.querySelector('.trace-section-body');
    const toggle = section.querySelector('.trace-toggle');
    if (body.style.display === 'none') {
        body.style.display = 'block';
        toggle.innerHTML = '&#9660;';
    } else {
        body.style.display = 'none';
        toggle.innerHTML = '&#9654;';
    }
};

// === Chat functions ===

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

    // Clear trace for new query
    clearTrace();
    setTraceStatus('Processing query...', true);

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
                let data;
                try { data = JSON.parse(line.slice(6)); } catch { continue; }

                if (data.type === 'content') {
                    fullContent += data.content;
                    contentDiv.innerHTML = marked.parse(fullContent);
                    chat.scrollTop = chat.scrollHeight;

                } else if (data.type === 'sources') {
                    sources = data.sources;

                } else if (data.type === 'debug') {
                    // Route debug events to the trace panel
                    const step = data.step || 'info';
                    const traceData = data.data || {};

                    if (step === 'system_info') {
                        addTraceSection('system', 'System Info', traceData);
                    } else if (step === 'query') {
                        addTraceSection('query', 'User Query', traceData);
                    } else if (step === 'rag_start') {
                        setTraceStatus('Searching RAG...', true);
                        addTraceSection('rag', 'RAG Search', traceData);
                    } else if (step === 'rag_results') {
                        addTraceSection('rag', `RAG Results (${traceData.matches || 0} matches)`, traceData);
                    } else if (step === 'rag_error') {
                        addTraceSection('error', 'RAG Error', traceData);
                    } else if (step === 'llm_prompt') {
                        setTraceStatus('Generating with LLM...', true);
                        addTraceSection('llm', 'LLM Prompt', traceData);
                    } else if (step === 'llm_start') {
                        addTraceSection('llm', 'LLM Streaming', traceData);
                    } else if (step === 'llm_done') {
                        setTraceStatus('Done', false);
                        addTraceSection('llm', 'LLM Complete', traceData);
                    } else if (step === 'llm_error') {
                        addTraceSection('error', 'LLM Error', traceData);
                    }

                } else if (data.type === 'error') {
                    contentDiv.innerHTML = `<div class="error">${escapeHtml(data.error)}</div>`;
                    addTraceSection('error', 'Error', { error: data.error, type: data.error_type });

                } else if (data.type === 'rag_error') {
                    addTraceSection('error', 'RAG Error', { error: data.error });
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
        addTraceSection('error', 'Network Error', { error: e.message });
    }

    btnSend.disabled = false;
    input.focus();
}

// Init
refreshStats();
input.focus();
// Show trace panel by default
btnToggleTrace.classList.add('active');
