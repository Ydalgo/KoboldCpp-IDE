"""Herramientas que el agente puede ejecutar (con sandbox dinámico)."""

import os
import subprocess
from pathlib import Path
from typing import Any

# Comandos bloqueados
BLOCKED_COMMANDS = [
    "sudo", "rm -rf /", "mkfs", "dd if=", ":(){:|:&};:",
    "chmod 777 /", "> /dev/sda", "shutdown", "reboot",
    "passwd", "chown root", "visudo",
]


def _resolve(root: Path, path: str) -> Path:
    """Resuelve una ruta y verifica que está dentro del sandbox."""
    p = (root / path).resolve()
    if not str(p).startswith(str(root.resolve())):
        raise PermissionError(f"Ruta fuera del sandbox: {path}")
    return p


# ── Implementación de las herramientas ───────────────────────
def tool_read_file(root: Path, path: str, **_kwargs) -> dict:
    try:
        p = _resolve(root, path)
        if not p.exists():
            return {"error": f"No existe: {path}"}
        if p.is_dir():
            return {"error": f"Es un directorio: {path}"}
        content = p.read_text(encoding="utf-8", errors="replace")
        if len(content) > 50_000:
            content = content[:50_000] + "\n[...truncado...]"
        return {"content": content}
    except Exception as e:
        return {"error": str(e)}


def tool_write_file(root: Path, path: str, content: str, **_kwargs) -> dict:
    try:
        p = _resolve(root, path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return {"ok": True, "path": path, "bytes": len(content)}
    except Exception as e:
        return {"error": str(e)}


def tool_list_dir(root: Path, path: str = ".", **_kwargs) -> dict:
    try:
        p = _resolve(root, path)
        if not p.exists():
            return {"error": f"No existe: {path}"}
        if not p.is_dir():
            return {"error": f"No es un directorio: {path}"}
        entries = []
        for child in sorted(p.iterdir()):
            entries.append({
                "name": child.name,
                "type": "dir" if child.is_dir() else "file",
                "size": child.stat().st_size if child.is_file() else None,
            })
        return {"entries": entries}
    except Exception as e:
        return {"error": str(e)}


def tool_run_command(root: Path, command: str, **_kwargs) -> dict:
    for blocked in BLOCKED_COMMANDS:
        if blocked in command:
            return {"error": f"Comando bloqueado: {blocked}"}
    try:
        result = subprocess.run(
            command, shell=True, cwd=str(root),
            capture_output=True, text=True, timeout=60,
        )
        return {
            "exit_code": result.returncode,
            "stdout": result.stdout[:8000],
            "stderr": result.stderr[:8000],
        }
    except subprocess.TimeoutExpired:
        return {"error": "Timeout (60s)"}
    except Exception as e:
        return {"error": str(e)}


# ── Registro ─────────────────────────────────────────────────
TOOL_IMPLS = {
    "read_file": tool_read_file,
    "write_file": tool_write_file,
    "list_dir": tool_list_dir,
    "run_command": tool_run_command,
}


# ── Esquemas (formato OpenAI tools) ──────────────────────────
TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Lee el contenido de un archivo dentro del proyecto.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Ruta relativa al proyecto"}
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Escribe contenido en un archivo. Crea los directorios que falten.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "content": {"type": "string"},
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_dir",
            "description": "Lista los archivos y carpetas de un directorio del proyecto.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Por defecto '.'"}
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_command",
            "description": "Ejecuta un comando shell en la raíz del proyecto.",
            "parameters": {
                "type": "object",
                "properties": {"command": {"type": "string"}},
                "required": ["command"],
            },
        },
    },
]


def execute_tool(root: Path, name: str, arguments: dict[str, Any]) -> dict:
    """Ejecuta una herramienta por nombre, con el sandbox dado."""
    if name not in TOOL_IMPLS:
        return {"error": f"Herramienta desconocida: {name}"}
    return TOOL_IMPLS[name](root, **arguments)
