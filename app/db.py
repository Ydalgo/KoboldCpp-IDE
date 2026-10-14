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
        # Crear tabla sessions
        await db.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                name TEXT NOT NULL DEFAULT '',
                workspace TEXT NOT NULL,
                system_prompt TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)

        # Migración: si la tabla existía sin columna 'name', añadirla
        cursor = await db.execute("PRAGMA table_info(sessions)")
        columns = [row[1] for row in await cursor.fetchall()]
        if 'name' not in columns:
            await db.execute("ALTER TABLE sessions ADD COLUMN name TEXT NOT NULL DEFAULT ''")

        await db.commit()


async def upsert_session(session_id: str, workspace: str, system_prompt: str, name: str = None):
    """Crea o actualiza los metadatos de una sesión."""
    now = datetime.utcnow().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        # Si la sesión ya existe y no se pasa name, mantener el actual
        if name is None:
            cursor = await db.execute(
                "SELECT name FROM sessions WHERE session_id = ?",
                (session_id,),
            )
            row = await cursor.fetchone()
            name = row[0] if row else ''

        await db.execute("""
            INSERT INTO sessions (session_id, name, workspace, system_prompt, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(session_id) DO UPDATE SET
                name = excluded.name,
                workspace = excluded.workspace,
                system_prompt = excluded.system_prompt,
                updated_at = excluded.updated_at
        """, (session_id, name, workspace, system_prompt, now, now))
        await db.commit()


async def get_session_meta(session_id: str) -> dict | None:
    """Devuelve los metadatos de una sesión o None."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT name, workspace, system_prompt FROM sessions WHERE session_id = ?",
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
    """Lista todas las sesiones con preview + workspace + name."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("""
            SELECT s.session_id,
                   s.name,
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
        
async def rename_session(session_id: str, name: str):
    """Renombra una sesión."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE sessions SET name = ?, updated_at = ? WHERE session_id = ?",
            (name, datetime.utcnow().isoformat(), session_id),
        )
        await db.commit()
