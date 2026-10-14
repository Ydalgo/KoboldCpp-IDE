// Estado global
let currentSession = null;
let isStreaming = false;

// ── Sesiones ────────────────────────────────────────────────
async function loadSessions() {
    const r = await fetch('/api/sessions');
    const sessions = await r.json();
    const container = document.getElementById('sessions');
    container.innerHTML = '';
    for (const s of sessions) {
        const div = document.createElement('div');
        div.className = 'session' + (s.session_id === currentSession ? ' active' : '');
        const wsName = (s.workspace || '').split('/').pop() || '—';
        div.innerHTML = `
            <span class="preview" title="${escapeHtml(s.workspace || '')}">
                ${escapeHtml(s.preview || s.session_id)}
                <br><small style="color:#666">📁 ${escapeHtml(wsName)}</small>
            </span>
            <span class="del" onclick="event.stopPropagation(); deleteSession('${s.session_id}')">×</span>
        `;
        div.onclick = () => openSession(s.session_id);
        container.appendChild(div);
    }
}

function newSession() {
    const id = 'sess-' + Date.now();
    currentSession = id;
    document.getElementById('messages').innerHTML = '';
    document.getElementById('session-title').textContent = id;
    loadSessions();
    document.getElementById('input').focus();
}

async function openSession(id) {
    currentSession = id;
    const r = await fetch(`/api/sessions/${id}`);
    const data = await r.json();
    const container = document.getElementById('messages');
    container.innerHTML = '';
    for (const m of data.messages) {
        if (m.role === 'tool') continue;
        addMessage(m.role, m.content);
    }
    document.getElementById('session-title').textContent = id;
    document.getElementById('session-workspace').textContent = '📁 ' + (data.meta.workspace || '—');
    loadSessions();
}

async function deleteSession(id) {
    if (!confirm('¿Borrar esta sesión?')) return;
    await fetch(`/api/sessions/${id}`, { method: 'DELETE' });
    if (currentSession === id) {
        currentSession = null;
        document.getElementById('messages').innerHTML = '';
        document.getElementById('session-title').textContent = '—';
        document.getElementById('session-workspace').textContent = '';
    }
    loadSessions();
}

// ── Mensajes ────────────────────────────────────────────────
function addMessage(role, content) {
    const div = document.createElement('div');
    div.className = 'msg ' + role;
    div.textContent = content;
    document.getElementById('messages').appendChild(div);
    scrollDown();
    return div;
}

function addToolBadge(name, args) {
    const div = document.createElement('div');
    div.className = 'msg tool-call';
    const argsStr = JSON.stringify(args, null, 0);
    div.innerHTML = `🔧 <b>${escapeHtml(name)}</b> <span class="args">${escapeHtml(argsStr.slice(0, 200))}</span>`;
    document.getElementById('messages').appendChild(div);
    scrollDown();
    return div;
}

function updateToolBadge(div, result) {
    const isError = result && result.error;
    div.classList.add(isError ? 'tool-error' : 'tool-ok');
    const summary = isError ? `❌ ${result.error}` : '✅';
    div.innerHTML += ` <span class="tool-result">${escapeHtml(summary.slice(0, 150))}</span>`;
}

function scrollDown() {
    const m = document.getElementById('messages');
    m.scrollTop = m.scrollHeight;
}

function escapeHtml(s) {
    const d = document.createElement('div');
    d.textContent = s == null ? '' : String(s);
    return d.innerHTML;
}

// ── Enviar mensaje ──────────────────────────────────────────
async function send() {
    if (isStreaming) return;
    const input = document.getElementById('input');
    const text = input.value.trim();
    if (!text) return;
    if (!currentSession) newSession();

    input.value = '';
    addMessage('user', text);

    const assistantDiv = addMessage('assistant', '');
    let assistantText = '';

    isStreaming = true;
    document.getElementById('send').disabled = true;

    try {
        const response = await fetch('/api/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ session_id: currentSession, message: text }),
        });
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        let currentToolDiv = null;

        while (true) {
            const { value, done } = await reader.read();
            if (done) break;
            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n');
            buffer = lines.pop() || '';
            for (const line of lines) {
                if (!line.startsWith('data: ')) continue;
                const payload = line.slice(6);
                if (payload === '[DONE]') continue;
                let evt;
                try { evt = JSON.parse(payload); } catch { continue; }

                if (evt.type === 'text') {
                    assistantText += evt.content;
                    assistantDiv.textContent = assistantText;
                    scrollDown();
                } else if (evt.type === 'tool_call') {
                    currentToolDiv = addToolBadge(evt.name, evt.args);
                } else if (evt.type === 'tool_result') {
                    if (currentToolDiv) {
                        updateToolBadge(currentToolDiv, evt.result);
                        currentToolDiv = null;
                    }
                } else if (evt.type === 'error') {
                    assistantDiv.className = 'msg error';
                    assistantDiv.textContent = 'Error: ' + evt.error;
                }
            }
        }
    } catch (e) {
        assistantDiv.className = 'msg error';
        assistantDiv.textContent = 'Error de conexión: ' + e.message;
    } finally {
        isStreaming = false;
        document.getElementById('send').disabled = false;
        loadSessions();
    }
}

// ── Estado del backend ──────────────────────────────────────
async function checkStatus() {
    try {
        const r = await fetch('/api/status');
        const data = await r.json();
        const dot = document.getElementById('status-dot');
        const text = document.getElementById('status-text');
        const model = document.getElementById('status-model');
        if (data.ok) {
            dot.className = 'status-dot ok';
            text.textContent = 'KoboldCpp conectado';
            model.textContent = data.models.join(', ');
        } else {
            dot.className = 'status-dot error';
            text.textContent = 'KoboldCpp no responde';
            model.textContent = data.error;
        }
    } catch (e) {
        document.getElementById('status-dot').className = 'status-dot error';
        document.getElementById('status-text').textContent = 'Error de conexión';
    }
}

// ── Config modal (LLM) ──────────────────────────────────────
async function openConfig() {
    const cfg = await (await fetch('/api/config')).json();
    document.getElementById('cfg-base-url').value = cfg.base_url;
    document.getElementById('cfg-model').value = cfg.model;
    document.getElementById('cfg-api-key').value = cfg.api_key;
    document.getElementById('cfg-temperature').value = cfg.temperature;
    document.getElementById('cfg-max-tokens').value = cfg.max_tokens;
    document.getElementById('config-modal').classList.add('open');
}

function closeConfig() {
    document.getElementById('config-modal').classList.remove('open');
}

async function saveConfig() {
    const cfg = {
        base_url: document.getElementById('cfg-base-url').value,
        model: document.getElementById('cfg-model').value,
        api_key: document.getElementById('cfg-api-key').value,
        temperature: parseFloat(document.getElementById('cfg-temperature').value),
        max_tokens: parseInt(document.getElementById('cfg-max-tokens').value),
        max_iterations: 15,
    };
    await fetch('/api/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(cfg),
    });
    closeConfig();
    checkStatus();
}

// ── Session modal (workspace + prompt) ──────────────────────
async function openSessionConfig() {
    if (!currentSession) {
        alert('Crea o abre una sesión primero.');
        return;
    }
    const r = await fetch(`/api/sessions/${currentSession}`);
    const data = await r.json();
    document.getElementById('sess-workspace').value = data.meta.workspace || '';
    document.getElementById('sess-prompt').value = data.meta.system_prompt || '';
    document.getElementById('session-modal').classList.add('open');
}

function closeSessionConfig() {
    document.getElementById('session-modal').classList.remove('open');
}

async function saveSessionConfig() {
    if (!currentSession) return;
    const payload = {
        workspace: document.getElementById('sess-workspace').value.trim(),
        system_prompt: document.getElementById('sess-prompt').value,
    };
    const r = await fetch(`/api/sessions/${currentSession}/meta`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
    });
    if (!r.ok) {
        const err = await r.json();
        alert('Error: ' + (err.detail || 'desconocido'));
        return;
    }
    const data = await r.json();
    document.getElementById('session-workspace').textContent = '📁 ' + data.workspace;
    closeSessionConfig();
}

// ── Eventos ─────────────────────────────────────────────────
document.getElementById('input').addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        send();
    }
});

setInterval(checkStatus, 15000);

(async () => {
    await checkStatus();
    await loadSessions();
    document.getElementById('input').focus();
})();
