"""Capa de persistencia con SQLite (async)."""

import aiosqlite
from pathlib import Path
from datetime import datetime

DB_PATH = Path(__file__).parent.parent / "data" / "history.db"


async def init_db():
    """Crea las tablas si no existen."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_session ON messages(session_id, id)
        """)
        # Nueva tabla: metadatos por sesión
        await db.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                workspace TEXT NOT NULL,
                system_prompt TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        await db.commit()


async def upsert_session(session_id: str, workspace: str, system_prompt: str):
    """Crea o actualiza los metadatos de una sesión."""
    now = datetime.utcnow().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO sessions (session_id, workspace, system_prompt, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(session_id) DO UPDATE SET
                workspace = excluded.workspace,
                system_prompt = excluded.system_prompt,
                updated_at = excluded.updated_at
        """, (session_id, workspace, system_prompt, now, now))
        await db.commit()


async def get_session_meta(session_id: str) -> dict | None:
    """Devuelve los metadatos de una sesión o None."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT workspace, system_prompt FROM sessions WHERE session_id = ?",
            (session_id,),
        )
        row = await cursor.fetchone()
        return dict(row) if row else None


async def save_message(session_id: str, role: str, content: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO messages (session_id, role, content, created_at) VALUES (?, ?, ?, ?)",
            (session_id, role, content, datetime.utcnow().isoformat()),
        )
        await db.commit()


async def get_messages(session_id: str, limit: int = 100):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT role, content, created_at FROM messages "
            "WHERE session_id = ? ORDER BY id ASC LIMIT ?",
            (session_id, limit),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]


async def list_sessions():
    """Lista todas las sesiones con preview + workspace."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("""
            SELECT s.session_id,
                   s.workspace,
                   s.updated_at as started_at,
                   (SELECT COUNT(*) FROM messages m WHERE m.session_id = s.session_id) as count,
                   (SELECT content FROM messages m
                    WHERE m.session_id = s.session_id AND m.role = 'user'
                    ORDER BY id ASC LIMIT 1) as preview
            FROM sessions s
            ORDER BY s.updated_at DESC
        """)
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]


async def delete_session(session_id: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
        await db.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
        await db.commit()
