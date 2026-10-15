// ══════════════════════════════════════════════════════════════
//  Estado global
// ══════════════════════════════════════════════════════════════
let currentSession = null;
let isStreaming = false;
let editor = null;
let openTabs = [];
let activeTabPath = null;

// ══════════════════════════════════════════════════════════════
//  Detección de lenguaje
// ══════════════════════════════════════════════════════════════
function detectLang(path) {
    if (!path) return 'plaintext';
    const ext = path.split('.').pop().toLowerCase();
    const map = {
        py: 'python', js: 'javascript', ts: 'typescript', jsx: 'javascript',
        tsx: 'typescript', json: 'json', md: 'markdown', html: 'html',
        css: 'css', sh: 'shell', bash: 'shell', yml: 'yaml', yaml: 'yaml',
        toml: 'ini', ini: 'ini', sql: 'sql', go: 'go', rs: 'rust',
        java: 'java', c: 'c', cpp: 'cpp', h: 'c', xml: 'xml',
        txt: 'plaintext', gitignore: 'plaintext',
    };
    return map[ext] || 'plaintext';
}

// ══════════════════════════════════════════════════════════════
//  Monaco init
// ══════════════════════════════════════════════════════════════
require.config({ paths: { vs: 'https://cdn.jsdelivr.net/npm/monaco-editor@0.52.0/min/vs' } });

require(['vs/editor/editor.main'], function () {
    editor = monaco.editor.create(document.getElementById('editor'), {
        value: '',
        language: 'plaintext',
        theme: 'vs-dark',
        automaticLayout: true,
        fontSize: 13,
        minimap: { enabled: false },
        scrollBeyondLastLine: false,
        renderWhitespace: 'selection',
        tabSize: 4,
    });

    editor.onDidChangeModelContent(() => {
        if (!activeTabPath) return;
        const tab = openTabs.find(t => t.path === activeTabPath);
        if (!tab) return;
        const current = editor.getValue();
        tab.dirty = current !== tab.savedContent;
        renderTabs();
        updateStatusBar();
    });

    editor.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.KeyS, () => saveCurrentFile());

    updateStatusBar();
    init();
});

// ══════════════════════════════════════════════════════════════
//  Árbol de archivos
// ══════════════════════════════════════════════════════════════
async function refreshTree() {
    const container = document.getElementById('file-tree');
    if (!currentSession) {
        container.innerHTML = '<div style="padding:12px;color:#666;font-size:11px">Sin sesión activa</div>';
        return;
    }
    container.innerHTML = '<div style="padding:8px;color:#666;font-size:11px">Cargando…</div>';
    try {
        const r = await fetch(`/api/files/tree?session_id=${currentSession}&path=.`);
        if (!r.ok) throw new Error(await r.text());
        const data = await r.json();
        container.innerHTML = '';
        if (!data.entries.length) {
            container.innerHTML = '<div style="padding:8px;color:#666;font-size:11px">Carpeta vacía</div>';
            return;
        }
        for (const entry of data.entries) {
            container.appendChild(makeTreeItem(entry, 0));
        }
    } catch (e) {
        container.innerHTML = `<div style="padding:8px;color:#f48771;font-size:11px">Error: ${e.message}</div>`;
    }
}

function applyPanelState(state) {
    // Solo cambiamos el grid-template-columns; no usamos clases que hagan display:none
    updateGridTemplate(state);

    // Mostrar/ocultar botones de "mostrar panel"
    const btnShowExplorer = document.getElementById('btn-show-explorer');
    const btnShowChat = document.getElementById('btn-show-chat');
    if (btnShowExplorer) btnShowExplorer.style.display = state.collapseExplorer ? 'inline-block' : 'none';
    if (btnShowChat) btnShowChat.style.display = state.collapseChat ? 'inline-block' : 'none';

    // Ajustar el editor si cambia el tamaño
    if (editor) setTimeout(() => editor.layout(), 200);
}

function makeTreeItem(entry, depth) {
    const wrapper = document.createElement('div');
    const item = document.createElement('div');
    item.className = 'tree-item' + (entry.type === 'dir' ? ' dir' : '');
    item.style.paddingLeft = (8 + depth * 14) + 'px';
    item.dataset.path = entry.path;

    const icon = entry.type === 'dir' ? '📁' : '📄';
    item.innerHTML = `<span class="icon">${icon}</span><span class="name">${escapeHtml(entry.name)}</span>`;

    if (entry.type === 'dir') {
        const children = document.createElement('div');
        children.className = 'tree-children';
        item.onclick = async () => {
            children.classList.toggle('open');
            item.classList.toggle('active', children.classList.contains('open'));
            if (children.classList.contains('open') && !children.dataset.loaded) {
                try {
                    const r = await fetch(`/api/files/tree?session_id=${currentSession}&path=${encodeURIComponent(entry.path)}`);
                    const data = await r.json();
                    for (const child of data.entries) {
                        children.appendChild(makeTreeItem(child, depth + 1));
                    }
                    children.dataset.loaded = '1';
                } catch (e) {
                    console.error(e);
                }
            }
        };
        wrapper.appendChild(item);
        wrapper.appendChild(children);
    } else {
        item.onclick = () => openFile(entry.path);
        wrapper.appendChild(item);
    }
    return wrapper;
}

function highlightTreeItem(path) {
    document.querySelectorAll('.tree-item').forEach(el => el.classList.remove('active'));
    const el = document.querySelector(`.tree-item[data-path="${path}"]`);
    if (el) el.classList.add('active');
}

// ══════════════════════════════════════════════════════════════
//  Abrir / cerrar / guardar archivos
// ══════════════════════════════════════════════════════════════
async function openFile(path) {
    let tab = openTabs.find(t => t.path === path);
    if (!tab) {
        try {
            const r = await fetch(`/api/files/read?session_id=${currentSession}&path=${encodeURIComponent(path)}`);
            if (!r.ok) throw new Error(await r.text());
            const data = await r.json();
            tab = { path, content: data.content, savedContent: data.content, dirty: false };
            openTabs.push(tab);
        } catch (e) {
            alert('No se pudo leer el archivo: ' + e.message);
            return;
        }
    }
    activeTabPath = path;
    renderTabs();
    showTabInEditor(tab);
    highlightTreeItem(path);
}

function showTabInEditor(tab) {
    const lang = detectLang(tab.path);
    const model = monaco.editor.createModel(tab.content, lang);
    editor.setModel(model);
    updateStatusBar();
}

function renderTabs() {
    const container = document.getElementById('tabs');
    container.innerHTML = '';
    for (const tab of openTabs) {
        const div = document.createElement('div');
        div.className = 'tab' + (tab.path === activeTabPath ? ' active' : '');
        const name = tab.path.split('/').pop();
        div.innerHTML = `<span>${escapeHtml(name)}</span>${tab.dirty ? '<span class="dirty">●</span>' : ''}<span class="close" onclick="event.stopPropagation(); closeTab('${tab.path}')">×</span>`;
        div.title = tab.path;
        div.onclick = () => {
            activeTabPath = tab.path;
            renderTabs();
            showTabInEditor(tab);
            highlightTreeItem(tab.path);
        };
        container.appendChild(div);
    }
}

function closeTab(path) {
    const idx = openTabs.findIndex(t => t.path === path);
    if (idx === -1) return;
    if (openTabs[idx].dirty && !confirm('Este archivo tiene cambios sin guardar. ¿Cerrar de todas formas?')) return;
    openTabs.splice(idx, 1);
    if (activeTabPath === path) {
        activeTabPath = openTabs.length ? openTabs[openTabs.length - 1].path : null;
        if (activeTabPath) {
            showTabInEditor(openTabs.find(t => t.path === activeTabPath));
        } else {
            editor.setModel(monaco.editor.createModel('', 'plaintext'));
        }
    }
    renderTabs();
    updateStatusBar();
}

async function saveCurrentFile() {
    if (!activeTabPath) return;
    const tab = openTabs.find(t => t.path === activeTabPath);
    if (!tab) return;
    const content = editor.getValue();
    try {
        const r = await fetch('/api/files/write', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ session_id: currentSession, path: tab.path, content }),
        });
        if (!r.ok) throw new Error(await r.text());
        tab.savedContent = content;
        tab.content = content;
        tab.dirty = false;
        renderTabs();
        updateStatusBar();
    } catch (e) {
        alert('Error guardando: ' + e.message);
    }
}

function updateStatusBar() {
    const tab = openTabs.find(t => t.path === activeTabPath);
    const dirty = tab && tab.dirty;

    document.getElementById('status-file').textContent = tab ? tab.path : 'Sin archivo abierto';
    document.getElementById('status-dirty').style.display = dirty ? 'inline-block' : 'none';
    document.getElementById('status-lang').textContent = tab ? detectLang(tab.path) : '';

    // Mostrar/ocultar el botón de guardar
    const btnSave = document.getElementById('btn-save');
    if (btnSave) {
        btnSave.style.display = dirty ? 'inline-block' : 'none';
    }
}

// ══════════════════════════════════════════════════════════════
//  Sesiones
// ══════════════════════════════════════════════════════════════
function onSessionSelect(id) {
    if (!id) return;
    openSession(id);
}

async function newSession() {
    const id = 'sess-' + Date.now();
    const defaultName = 'Sesión ' + new Date().toLocaleTimeString('es-ES', {hour: '2-digit', minute:'2-digit'});
    const name = prompt('Nombre de la nueva sesión:', defaultName);
    if (name === null) return;  // Cancelado

    currentSession = id;
    openTabs = [];
    activeTabPath = null;
    if (editor) editor.setModel(monaco.editor.createModel('', 'plaintext'));
    renderTabs();
    document.getElementById('messages').innerHTML = '';
    document.getElementById('session-title').textContent = id;
    document.getElementById('session-workspace').textContent = '';
    loadSessions();
    refreshTree();
    document.getElementById('input').focus();
    // Guardar el nombre
    try {
        await fetch(`/api/sessions/${currentSession}/rename`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name: name.trim() || defaultName }),
        });
    } catch (e) {}
}

async function openSession(id) {
    currentSession = id;
    openTabs = [];
    activeTabPath = null;
    if (editor) editor.setModel(monaco.editor.createModel('', 'plaintext'));
    renderTabs();

    const r = await fetch(`/api/sessions/${id}`);
    const data = await r.json();
    const container = document.getElementById('messages');
    container.innerHTML = '';
    for (const m of data.messages) {
        if (m.role === 'tool') continue;
        addMessage(m.role, m.content);
    }
    document.getElementById('session-title').textContent = data.meta.name || id;
	document.getElementById('session-workspace').textContent = '📁 ' + (data.meta.workspace || '—');
    loadSessions();
    refreshTree();
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

// ══════════════════════════════════════════════════════════════
//  Chat
// ══════════════════════════════════════════════════════════════
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
    const argsStr = JSON.stringify(args);
    div.innerHTML = `🔧 <b>${escapeHtml(name)}</b> <span class="args">${escapeHtml(argsStr.slice(0, 150))}</span>`;
    document.getElementById('messages').appendChild(div);
    scrollDown();
    return div;
}

function updateToolBadge(div, result) {
    const isError = result && result.error;
    div.classList.add(isError ? 'tool-error' : 'tool-ok');
    const summary = isError ? `❌ ${result.error}` : '✅';
    div.innerHTML += ` <span class="tool-result">${escapeHtml(summary.slice(0, 120))}</span>`;
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
                    if (evt.name === 'write_file' || evt.name === 'run_command') {
                        refreshTree();
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
        refreshTree();
    }
}

// ══════════════════════════════════════════════════════════════
//  Estado del backend
// ══════════════════════════════════════════════════════════════
async function checkStatus() {
    try {
        const r = await fetch('/api/status');
        const data = await r.json();
        const dot = document.getElementById('status-dot');
        const text = document.getElementById('status-text');
        if (data.ok) {
            dot.className = 'status-dot ok';
            text.textContent = 'KoboldCpp conectado';
        } else {
            dot.className = 'status-dot error';
            text.textContent = 'No responde';
        }
    } catch (e) {
        document.getElementById('status-dot').className = 'status-dot error';
        document.getElementById('status-text').textContent = 'Error';
    }
}

// ══════════════════════════════════════════════════════════════
//  Modales
// ══════════════════════════════════════════════════════════════
async function openLLMConfig() {
    const cfg = await (await fetch('/api/config')).json();
    document.getElementById('cfg-base-url').value = cfg.base_url;
    document.getElementById('cfg-model').value = cfg.model;
    document.getElementById('cfg-api-key').value = cfg.api_key;
    document.getElementById('cfg-temperature').value = cfg.temperature;
    document.getElementById('cfg-max-tokens').value = cfg.max_tokens;
    document.getElementById('config-modal').classList.add('open');
}

function closeLLMConfig() {
    document.getElementById('config-modal').classList.remove('open');
}

async function saveLLMConfig() {
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
    closeLLMConfig();
    checkStatus();
}

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
    try {
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
        refreshTree();
    } catch (e) {
        alert('Error: ' + e.message);
    }
}

// ══════════════════════════════════════════════════════════════
//  Inicialización
// ══════════════════════════════════════════════════════════════
async function init() {
    document.getElementById('input').addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            send();
        }
    });
    setInterval(checkStatus, 15000);
    window.addEventListener('beforeunload', (e) => {
        const hasDirty = openTabs.some(t => t.dirty);
        if (hasDirty) {
            e.preventDefault();
            e.returnValue = '';
            return '';
        }
    });

    // ← AÑADE ESTA LÍNEA
    initResizers();

    await checkStatus();
    await loadSessions();
    document.getElementById('input').focus();
}

async function renameCurrentSession() {
    if (!currentSession) {
        alert('No hay sesión activa.');
        return;
    }
    // Obtener el nombre actual para ponerlo por defecto
    let currentName = '';
    try {
        const r = await fetch(`/api/sessions/${currentSession}`);
        const data = await r.json();
        currentName = data.meta.name || '';
    } catch (e) {}

    const newName = prompt('Nuevo nombre de la sesión:', currentName || currentSession);
    if (newName === null) return;  // Cancelado
    const trimmed = newName.trim();
    if (!trimmed) {
        alert('El nombre no puede estar vacío.');
        return;
    }

    try {
        const r = await fetch(`/api/sessions/${currentSession}/rename`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name: trimmed }),
        });
        if (!r.ok) throw new Error(await r.text());
        document.getElementById('session-title').textContent = trimmed;
        loadSessions();
    } catch (e) {
        alert('Error renombrando: ' + e.message);
    }
}

// ══════════════════════════════════════════════════════════════
//  Paneles redimensionables y colapsables
// ══════════════════════════════════════════════════════════════
const PANEL_STATE_KEY = 'agent-dashboard-panel-state-v1';

function loadPanelState() {
    try {
        const raw = localStorage.getItem(PANEL_STATE_KEY);
        if (raw) return JSON.parse(raw);
    } catch (e) {}
    return { explorerWidth: 240, chatWidth: 380, collapseExplorer: false, collapseChat: false };
}

function savePanelState(state) {
    try {
        localStorage.setItem(PANEL_STATE_KEY, JSON.stringify(state));
    } catch (e) {}
}

function updateGridTemplate(state) {
    const app = document.getElementById('app');
    if (!app) return;
    const eW = state.collapseExplorer ? 0 : state.explorerWidth;
    const cW = state.collapseChat ? 0 : state.chatWidth;
    const eR = state.collapseExplorer ? 0 : 4;
    const cR = state.collapseChat ? 0 : 4;
    app.style.gridTemplateColumns = `${eW}px ${eR}px 1fr ${cR}px ${cW}px`;
}

function togglePanel(which) {
    const state = loadPanelState();
    if (which === 'explorer') state.collapseExplorer = !state.collapseExplorer;
    if (which === 'chat') state.collapseChat = !state.collapseChat;
    savePanelState(state);
    applyPanelState(state);
}

function initResizers() {
    const state = loadPanelState();
    applyPanelState(state);

    // Resizer izquierdo (sidebar <-> editor)
    const resizerLeft = document.getElementById('resizer-left');
    if (resizerLeft) {
        resizerLeft.addEventListener('mousedown', (e) => startDrag(e, 'left'));
    }

    // Resizer derecho (editor <-> chat)
    const resizerRight = document.getElementById('resizer-right');
    if (resizerRight) {
        resizerRight.addEventListener('mousedown', (e) => startDrag(e, 'right'));
    }
}

async function loadSessions() {
    const r = await fetch('/api/sessions');
    const sessions = await r.json();
    const select = document.getElementById('session-select');
    select.innerHTML = '<option value="">— Elegir —</option>';
    for (const s of sessions) {
        const opt = document.createElement('option');
        opt.value = s.session_id;
        // Si hay nombre, mostrarlo. Si no, mostrar el preview del primer mensaje (o el ID)
        const label = s.name
            ? s.name
            : (s.preview ? s.preview.slice(0, 50) : s.session_id);
        opt.textContent = label;
        if (s.session_id === currentSession) opt.selected = true;
        select.appendChild(opt);
    }
}

function startDrag(e, side) {
    e.preventDefault();
    const resizer = e.currentTarget;
    resizer.classList.add('dragging');
    const startX = e.clientX;
    const state = loadPanelState();
    const startWidth = side === 'left' ? state.explorerWidth : state.chatWidth;

    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';

    function onMove(ev) {
        const delta = side === 'left' ? ev.clientX - startX : startX - ev.clientX;
        const newWidth = Math.max(150, Math.min(600, startWidth + delta));
        if (side === 'left') state.explorerWidth = newWidth;
        else state.chatWidth = newWidth;
        updateGridTemplate(state);
        if (editor) editor.layout();
    }

    function onUp() {
        resizer.classList.remove('dragging');
        document.body.style.cursor = '';
        document.body.style.userSelect = '';
        savePanelState(state);
        document.removeEventListener('mousemove', onMove);
        document.removeEventListener('mouseup', onUp);
    }

    document.addEventListener('mousemove', onMove);
    document.addEventListener('mouseup', onUp);
}


// ══════════════════════════════════════════════════════════════
//  Explorador de carpetas del sistema
// ══════════════════════════════════════════════════════════════
let fsCurrentPath = null;
let fsCurrentParent = null;

async function openFsBrowser(startPath = null) {
    const input = document.getElementById('sess-workspace');
    const initial = startPath || input.value.trim() || null;
    document.getElementById('fs-modal').classList.add('open');
    await fsNavigate(initial);
}

function closeFsBrowser() {
    document.getElementById('fs-modal').classList.remove('open');
}

async function fsNavigate(path) {
    const list = document.getElementById('fs-list');
    list.innerHTML = '<div style="padding:8px;color:#666;font-size:12px">Cargando…</div>';

    try {
        const url = path
            ? `/api/fs/browse?path=${encodeURIComponent(path)}`
            : `/api/fs/browse`;
        const r = await fetch(url);
        if (!r.ok) {
            const err = await r.json().catch(() => ({}));
            throw new Error(err.detail || `Error ${r.status}`);
        }
        const data = await r.json();

        fsCurrentPath = data.path;
        fsCurrentParent = data.parent;

        document.getElementById('fs-path').value = data.path;

        list.innerHTML = '';

        if (data.entries.length === 0) {
            list.innerHTML = '<div style="padding:8px;color:#666;font-size:12px">(Carpeta vacía)</div>';
        } else {
            for (const entry of data.entries) {
                const item = document.createElement('div');
                item.style.cssText = 'padding:6px 10px;cursor:pointer;font-size:13px;display:flex;align-items:center;gap:8px;border-radius:3px';
                item.innerHTML = `<span>📁</span><span>${escapeHtml(entry.name)}</span>`;
                item.onmouseenter = () => item.style.background = '#2a2d2e';
                item.onmouseleave = () => item.style.background = '';
                item.ondblclick = () => fsNavigate(entry.path);
                item.onclick = () => {
                    list.querySelectorAll('div').forEach(el => el.style.background = '');
                    item.style.background = '#094771';
                };
                list.appendChild(item);
            }
        }
    } catch (e) {
        list.innerHTML = `<div style="padding:8px;color:#f48771;font-size:12px">Error: ${escapeHtml(e.message)}</div>`;
    }
}

async function fsGoHome() {
    fsCurrentPath = null;
    await fsNavigate(null);
}

async function fsGoUp() {
    if (fsCurrentParent) {
        await fsNavigate(fsCurrentParent);
    }
}

async function fsRefresh() {
    if (fsCurrentPath) {
        await fsNavigate(fsCurrentPath);
    }
}

function fsSelectCurrent() {
    if (!fsCurrentPath) return;
    document.getElementById('sess-workspace').value = fsCurrentPath;
    closeFsBrowser();
}
