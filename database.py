"""
لایه دیتابیس - SQLite
جدول‌ها:
- files: کدهای یکتا و مسیر فایل در کانال ذخیره‌سازی
- force_channels: کانال‌های جوین اجباری
"""

import sqlite3
import uuid
from contextlib import contextmanager

from config import DB_PATH


def init_db():
    with get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS files (
                code TEXT PRIMARY KEY,
                storage_message_id INTEGER NOT NULL,
                caption TEXT,
                file_name TEXT,
                added_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS force_channels (
                channel_id TEXT PRIMARY KEY,
                title TEXT,
                invite_link TEXT
            )
        """)
        conn.commit()


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


# ---------- فایل‌ها ----------

def add_file(storage_message_id: int, caption: str, file_name: str) -> str:
    code = uuid.uuid4().hex[:10]
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO files (code, storage_message_id, caption, file_name) VALUES (?, ?, ?, ?)",
            (code, storage_message_id, caption, file_name),
        )
        conn.commit()
    return code


def get_file(code: str):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM files WHERE code = ?", (code,)).fetchone()
        return dict(row) if row else None


def delete_file(code: str) -> bool:
    with get_conn() as conn:
        cur = conn.execute("DELETE FROM files WHERE code = ?", (code,))
        conn.commit()
        return cur.rowcount > 0


def list_files(limit: int = 50, offset: int = 0):
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM files ORDER BY added_at DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()
        return [dict(r) for r in rows]


def count_files() -> int:
    with get_conn() as conn:
        return conn.execute("SELECT COUNT(*) FROM files").fetchone()[0]


# ---------- کانال‌های جوین اجباری ----------

def add_force_channel(channel_id: str, title: str, invite_link: str = ""):
    with get_conn() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO force_channels (channel_id, title, invite_link) VALUES (?, ?, ?)",
            (channel_id, title, invite_link),
        )
        conn.commit()


def remove_force_channel(channel_id: str) -> bool:
    with get_conn() as conn:
        cur = conn.execute("DELETE FROM force_channels WHERE channel_id = ?", (channel_id,))
        conn.commit()
        return cur.rowcount > 0


def list_force_channels():
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM force_channels").fetchall()
        return [dict(r) for r in rows]
