"""Capa de persistencia con SQLite (async).

Modelo:
    projects  → carpetas de trabajo registradas
    sessions  → conversaciones con el agente (pertenecen a un proyecto o no)
    messages  → mensajes individuales de cada sesión
"""

import aiosqlite
from pathlib import Path
from datetime import datetime

DB_PATH = Path(__file__).parent.parent / "data" / "history.db"


# ══════════════════════════════════════════════════════════════
#  Init / migraciones
# ══════════════════════════════════════════════════════════════
async def init_db():
    """Crea las tablas si no existen."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        # ── projects ─────────────────────────────────────────
        await db.execute("""
            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                path TEXT NOT NULL UNIQUE,
                color TEXT NOT NULL DEFAULT '#4ec9b0',
                created_at TEXT NOT NULL,
                last_opened_at TEXT
            )
        """)

        # ── sessions ─────────────────────────────────────────
        await db.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                project_id INTEGER,
                name TEXT NOT NULL DEFAULT '',
                system_prompt TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE SET NULL
            )
        """)
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_sessions_project
            ON sessions(project_id, updated_at DESC)
        """)

        # ── messages ─────────────────────────────────────────
        await db.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
            )
        """)
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_messages_session
            ON messages(session_id, id)
        """)

        await db.commit()


# ══════════════════════════════════════════════════════════════
#  Proyectos
# ══════════════════════════════════════════════════════════════
def _now() -> str:
    return datetime.utcnow().isoformat()


async def list_projects() -> list[dict]:
    """Devuelve todos los proyectos con el número de sesiones."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("""
            SELECT p.id, p.name, p.path, p.color, p.created_at, p.last_opened_at,
                   (SELECT COUNT(*) FROM sessions s WHERE s.project_id = p.id) AS session_count
            FROM projects p
            ORDER BY p.last_opened_at DESC NULLS LAST, p.name ASC
        """)
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]


async def get_project(project_id: int) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT id, name, path, color, created_at, last_opened_at FROM projects WHERE id = ?",
            (project_id,),
        )
        row = await cursor.fetchone()
        return dict(row) if row else None


async def get_project_by_path(path: str) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT id, name, path, color, created_at, last_opened_at FROM projects WHERE path = ?",
            (path,),
        )
        row = await cursor.fetchone()
        return dict(row) if row else None


async def create_project(name: str, path: str, color: str = "#4ec9b0") -> dict:
    """Crea un proyecto. Devuelve el proyecto creado."""
    now = _now()
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "INSERT INTO projects (name, path, color, created_at, last_opened_at) VALUES (?, ?, ?, ?, ?)",
            (name, path, color, now, now),
        )
        await db.commit()
        project_id = cursor.lastrowid
    return await get_project(project_id)


async def get_or_create_project(path: str, name: str | None = None, color: str = "#4ec9b0") -> dict:
    """Si existe un proyecto con ese path, lo devuelve. Si no, lo crea."""
    existing = await get_project_by_path(path)
    if existing:
        return existing
    if not name:
        name = Path(path).name or path
    return await create_project(name, path, color)


async def update_project(project_id: int, name: str | None = None, color: str | None = None) -> dict | None:
    """Actualiza nombre y/o color de un proyecto."""
    fields = []
    values = []
    if name is not None:
        fields.append("name = ?")
        values.append(name)
    if color is not None:
        fields.append("color = ?")
        values.append(color)
    if not fields:
        return await get_project(project_id)

    values.append(project_id)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(f"UPDATE projects SET {', '.join(fields)} WHERE id = ?", values)
        await db.commit()
    return await get_project(project_id)


async def touch_project(project_id: int):
    """Actualiza last_opened_at."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE projects SET last_opened_at = ? WHERE id = ?",
            (_now(), project_id),
        )
        await db.commit()


async def delete_project(project_id: int):
    """Borra un proyecto. Las sesiones quedan sin proyecto (ON DELETE SET NULL)."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM projects WHERE id = ?", (project_id,))
        await db.commit()


# ══════════════════════════════════════════════════════════════
#  Sesiones
# ══════════════════════════════════════════════════════════════
async def list_sessions() -> list[dict]:
    """Todas las sesiones con info del proyecto asociado."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("""
            SELECT s.session_id, s.project_id, s.name, s.system_prompt,
                   s.created_at, s.updated_at,
                   p.name AS project_name, p.path AS project_path, p.color AS project_color,
                   (SELECT COUNT(*) FROM messages m WHERE m.session_id = s.session_id) AS message_count,
                   (SELECT content FROM messages m
                    WHERE m.session_id = s.session_id AND m.role = 'user'
                    ORDER BY m.id ASC LIMIT 1) AS preview
            FROM sessions s
            LEFT JOIN projects p ON p.id = s.project_id
            ORDER BY s.updated_at DESC
        """)
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]


async def list_sessions_by_project(project_id: int) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("""
            SELECT s.session_id, s.project_id, s.name, s.system_prompt,
                   s.created_at, s.updated_at,
                   (SELECT COUNT(*) FROM messages m WHERE m.session_id = s.session_id) AS message_count,
                   (SELECT content FROM messages m
                    WHERE m.session_id = s.session_id AND m.role = 'user'
                    ORDER BY m.id ASC LIMIT 1) AS preview
            FROM sessions s
            WHERE s.project_id = ?
            ORDER BY s.updated_at DESC
        """, (project_id,))
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]


async def get_session(session_id: str) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("""
            SELECT s.session_id, s.project_id, s.name, s.system_prompt,
                   s.created_at, s.updated_at,
                   p.name AS project_name, p.path AS project_path, p.color AS project_color
            FROM sessions s
            LEFT JOIN projects p ON p.id = s.project_id
            WHERE s.session_id = ?
        """, (session_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None


async def create_session(
    session_id: str,
    name: str = "",
    project_id: int | None = None,
    system_prompt: str = "",
) -> dict:
    """Crea una sesión nueva."""
    now = _now()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO sessions (session_id, project_id, name, system_prompt, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (session_id, project_id, name, system_prompt, now, now))
        await db.commit()
    return await get_session(session_id)


async def update_session(
    session_id: str,
    name: str | None = None,
    project_id: int | None = None,
    set_project: bool = False,
    system_prompt: str | None = None,
) -> dict | None:
    """Actualiza campos de una sesión.

    Si set_project=True, se actualiza project_id (aunque sea None).
    Si set_project=False, se ignora project_id.
    """
    fields = []
    values = []
    if name is not None:
        fields.append("name = ?")
        values.append(name)
    if set_project:
        fields.append("project_id = ?")
        values.append(project_id)
    if system_prompt is not None:
        fields.append("system_prompt = ?")
        values.append(system_prompt)

    if not fields:
        return await get_session(session_id)

    fields.append("updated_at = ?")
    values.append(_now())
    values.append(session_id)

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(f"UPDATE sessions SET {', '.join(fields)} WHERE session_id = ?", values)
        await db.commit()
    return await get_session(session_id)


async def delete_session(session_id: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
        await db.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
        await db.commit()


async def touch_session(session_id: str):
    """Actualiza updated_at (sin cambiar nada más)."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE sessions SET updated_at = ? WHERE session_id = ?",
            (_now(), session_id),
        )
        await db.commit()


# ══════════════════════════════════════════════════════════════
#  Mensajes
# ══════════════════════════════════════════════════════════════
async def save_message(session_id: str, role: str, content: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO messages (session_id, role, content, created_at) VALUES (?, ?, ?, ?)",
            (session_id, role, content, _now()),
        )
        await db.execute(
            "UPDATE sessions SET updated_at = ? WHERE session_id = ?",
            (_now(), session_id),
        )
        await db.commit()


async def get_messages(session_id: str, limit: int = 200) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT role, content, created_at FROM messages "
            "WHERE session_id = ? ORDER BY id ASC LIMIT ?",
            (session_id, limit),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]
