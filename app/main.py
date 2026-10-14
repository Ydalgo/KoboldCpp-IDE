"""Dashboard web con tool calling + workspace y system prompt por sesión."""

import json
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from . import db
from .kobold_client import KoboldClient
from .tools import TOOL_SCHEMAS, execute_tool

# ── Configuración global (defaults) ──────────────────────────
CONFIG = {
    "base_url": "http://127.0.0.1:5001/v1",
    "model": "koboldcpp/chat-qwen2.5-coder-32k",
    "api_key": "local",
    "temperature": 0.2,
    "max_tokens": 2048,
    "max_iterations": 15,
}

DEFAULT_WORKSPACE = str(Path.home() / "proyectos" / "pnt")

DEFAULT_SYSTEM_PROMPT = """Eres un desarrollador senior trabajando en un proyecto de software.

Responde SIEMPRE en español, de forma directa y concisa. No uses preámbulos como "Claro, voy a..." o "Por supuesto".

Tienes acceso a herramientas para:
- read_file: leer archivos
- write_file: crear o modificar archivos
- list_dir: listar directorios
- run_command: ejecutar comandos shell

REGLAS:
- Para crear o modificar código, usa SIEMPRE write_file. No lo devuelvas como texto.
- Antes de modificar un archivo, léelo primero con read_file.
- Cuando termines una tarea, resume brevemente qué hiciste y qué archivos tocaste.
- No pidas confirmación para acciones simples.
- No inventes contenido de archivos que no hayas leído.
- Si algo es ambiguo, pregunta antes de actuar."""

TEMPLATES_DIR = Path(__file__).parent / "templates"
STATIC_DIR = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    await db.init_db()
    yield


app = FastAPI(lifespan=lifespan)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
templates = Jinja2Templates(directory=TEMPLATES_DIR)


def get_client() -> KoboldClient:
    return KoboldClient(CONFIG["base_url"], CONFIG["model"], CONFIG["api_key"])


# ── Modelos Pydantic ─────────────────────────────────────────
class ChatRequest(BaseModel):
    session_id: str
    message: str


class ConfigUpdate(BaseModel):
    base_url: str
    model: str
    api_key: str = "local"
    temperature: float = 0.2
    max_tokens: int = 2048
    max_iterations: int = 15


class SessionUpdate(BaseModel):
    workspace: str
    system_prompt: str


# ── Rutas básicas ────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")


@app.get("/api/status")
async def status():
    try:
        models = await get_client().list_models()
        return {"ok": True, "models": models, "config": CONFIG}
    except Exception as e:
        return JSONResponse(status_code=503, content={"ok": False, "error": str(e)})


@app.get("/api/config")
async def get_config():
    return {
        **CONFIG,
        "default_workspace": DEFAULT_WORKSPACE,
        "default_system_prompt": DEFAULT_SYSTEM_PROMPT,
    }


@app.post("/api/config")
async def set_config(cfg: ConfigUpdate):
    CONFIG.update(cfg.model_dump())
    return {"ok": True, "config": CONFIG}


@app.get("/api/sessions")
async def sessions():
    return await db.list_sessions()


@app.get("/api/sessions/{session_id}")
async def session_messages(session_id: str):
    messages = await db.get_messages(session_id)
    meta = await db.get_session_meta(session_id) or {
        "workspace": DEFAULT_WORKSPACE,
        "system_prompt": DEFAULT_SYSTEM_PROMPT,
    }
    return {"messages": messages, "meta": meta}


@app.put("/api/sessions/{session_id}/meta")
async def update_session_meta(session_id: str, payload: SessionUpdate):
    # Validar workspace
    ws = Path(payload.workspace).expanduser().resolve()
    if not ws.exists() or not ws.is_dir():
        raise HTTPException(400, f"El workspace no existe o no es un directorio: {ws}")
    await db.upsert_session(session_id, str(ws), payload.system_prompt)
    return {"ok": True, "workspace": str(ws), "system_prompt": payload.system_prompt}


@app.delete("/api/sessions/{session_id}")
async def delete_session(session_id: str):
    await db.delete_session(session_id)
    return {"ok": True}


# ── Bucle agéntico ───────────────────────────────────────────
@app.post("/api/chat")
async def chat(req: ChatRequest):
    # Cargar metadatos de la sesión (o defaults)
    meta = await db.get_session_meta(req.session_id)
    workspace = Path(meta["workspace"]) if meta else Path(DEFAULT_WORKSPACE)
    system_prompt = meta["system_prompt"] if meta else DEFAULT_SYSTEM_PROMPT

    # Si la sesión no tenía metadatos, los creamos ahora
    if not meta:
        await db.upsert_session(req.session_id, str(workspace), system_prompt)

    await db.save_message(req.session_id, "user", req.message)
    history = await db.get_messages(req.session_id)

    messages = [{"role": "system", "content": system_prompt}]
    for m in history:
        messages.append({"role": m["role"], "content": m["content"]})

    async def generator():
        client = get_client()
        full_text = []
        iterations = 0

        try:
            while iterations < CONFIG["max_iterations"]:
                iterations += 1
                msg = await client.chat(
                    messages, tools=TOOL_SCHEMAS,
                    temperature=CONFIG["temperature"],
                    max_tokens=CONFIG["max_tokens"],
                )
                tool_calls = msg.get("tool_calls") or []
                content = msg.get("content") or ""

                if content:
                    full_text.append(content)
                    yield f"data: {json.dumps({'type': 'text', 'content': content})}\n\n"

                if not tool_calls:
                    break

                messages.append({"role": "assistant", "content": content, "tool_calls": tool_calls})

                for tc in tool_calls:
                    fn = tc.get("function", {})
                    name = fn.get("name", "?")
                    raw_args = fn.get("arguments", "{}")
                    try:
                        args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
                    except json.JSONDecodeError:
                        args = {}

                    yield f"data: {json.dumps({'type': 'tool_call', 'name': name, 'args': args})}\n\n"
                    result = execute_tool(workspace, name, args)
                    yield f"data: {json.dumps({'type': 'tool_result', 'name': name, 'result': result})}\n\n"

                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.get("id", name),
                        "content": json.dumps(result)[:4000],
                    })

            final = "".join(full_text)
            if final:
                await db.save_message(req.session_id, "assistant", final)
            yield "data: [DONE]\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"

    return StreamingResponse(generator(), media_type="text/event-stream")
