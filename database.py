import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

from config import DB_DIR, DB_PATH, CATEGORIES


def get_connection() -> sqlite3.Connection:
    DB_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Создаёт таблицы базы данных, если их ещё нет."""
    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                original_name TEXT NOT NULL,
                stored_name TEXT NOT NULL,
                category_key TEXT NOT NULL,
                category_title TEXT NOT NULL,
                version INTEGER NOT NULL,
                comment TEXT DEFAULT '',
                file_path TEXT NOT NULL,
                file_size INTEGER DEFAULT 0,
                telegram_file_id TEXT NOT NULL,
                uploaded_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS message_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                username TEXT,
                message_text TEXT,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_files_user ON files(user_id)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_files_name ON files(user_id, original_name)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_files_category ON files(user_id, category_key)"
        )
        conn.commit()


def now_iso() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def log_message(user_id: int, username: Optional[str], message_text: str) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO message_log (user_id, username, message_text, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (user_id, username, message_text, now_iso()),
        )
        conn.commit()


def get_next_version(user_id: int, original_name: str) -> int:
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT MAX(version) AS max_version
            FROM files
            WHERE user_id = ? AND LOWER(original_name) = LOWER(?)
            """,
            (user_id, original_name),
        ).fetchone()
    max_version = row["max_version"] if row else None
    return int(max_version or 0) + 1


def add_file(
    user_id: int,
    original_name: str,
    stored_name: str,
    category_key: str,
    version: int,
    comment: str,
    file_path: Path,
    file_size: int,
    telegram_file_id: str,
) -> int:
    category_title = CATEGORIES.get(category_key, "Другое")
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO files (
                user_id, original_name, stored_name, category_key, category_title,
                version, comment, file_path, file_size, telegram_file_id, uploaded_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                original_name,
                stored_name,
                category_key,
                category_title,
                version,
                comment,
                str(file_path),
                file_size,
                telegram_file_id,
                now_iso(),
            ),
        )
        conn.commit()
        return int(cursor.lastrowid)


def list_files(user_id: int, category_key: Optional[str] = None, limit: int = 50):
    with get_connection() as conn:
        if category_key:
            return conn.execute(
                """
                SELECT * FROM files
                WHERE user_id = ? AND category_key = ?
                ORDER BY uploaded_at DESC
                LIMIT ?
                """,
                (user_id, category_key, limit),
            ).fetchall()
        return conn.execute(
            """
            SELECT * FROM files
            WHERE user_id = ?
            ORDER BY uploaded_at DESC
            LIMIT ?
            """,
            (user_id, limit),
        ).fetchall()


def latest_files(user_id: int, limit: int = 5):
    return list_files(user_id, limit=limit)


def get_file_by_id(user_id: int, file_id: int):
    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM files WHERE user_id = ? AND id = ?",
            (user_id, file_id),
        ).fetchone()


def search_files(user_id: int, query: str, limit: int = 20):
    pattern = f"%{query}%"
    with get_connection() as conn:
        return conn.execute(
            """
            SELECT * FROM files
            WHERE user_id = ?
              AND (
                LOWER(original_name) LIKE LOWER(?)
                OR LOWER(comment) LIKE LOWER(?)
                OR LOWER(category_title) LIKE LOWER(?)
              )
            ORDER BY uploaded_at DESC
            LIMIT ?
            """,
            (user_id, pattern, pattern, pattern, limit),
        ).fetchall()


def get_versions_by_name(user_id: int, original_name: str):
    with get_connection() as conn:
        return conn.execute(
            """
            SELECT * FROM files
            WHERE user_id = ? AND LOWER(original_name) = LOWER(?)
            ORDER BY version DESC
            """,
            (user_id, original_name),
        ).fetchall()


def update_comment(user_id: int, file_id: int, new_comment: str) -> bool:
    with get_connection() as conn:
        cursor = conn.execute(
            """
            UPDATE files
            SET comment = ?
            WHERE user_id = ? AND id = ?
            """,
            (new_comment, user_id, file_id),
        )
        conn.commit()
        return cursor.rowcount > 0


def delete_file_record(user_id: int, file_id: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM files WHERE user_id = ? AND id = ?",
            (user_id, file_id),
        ).fetchone()
        if not row:
            return None
        conn.execute(
            "DELETE FROM files WHERE user_id = ? AND id = ?",
            (user_id, file_id),
        )
        conn.commit()
        return row


def get_category_stats(user_id: int):
    with get_connection() as conn:
        return conn.execute(
            """
            SELECT category_key, category_title, COUNT(*) AS count_files,
                   COALESCE(SUM(file_size), 0) AS total_size
            FROM files
            WHERE user_id = ?
            GROUP BY category_key, category_title
            ORDER BY count_files DESC
            """,
            (user_id,),
        ).fetchall()


def get_total_stats(user_id: int):
    with get_connection() as conn:
        return conn.execute(
            """
            SELECT COUNT(*) AS total_files,
                   COALESCE(SUM(file_size), 0) AS total_size,
                   COUNT(DISTINCT original_name) AS unique_names
            FROM files
            WHERE user_id = ?
            """,
            (user_id,),
        ).fetchone()

def get_next_auto_number(user_id: int, prefix: str) -> int:
    """
    Возвращает следующий номер для автоматического названия:
    photo_1, photo_2, document_1 и т.д.
    """
    pattern = f"{prefix}_%"

    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT COUNT(*) AS count_files
            FROM files
            WHERE user_id = ?
              AND LOWER(original_name) LIKE LOWER(?)
            """,
            (user_id, pattern),
        ).fetchone()

    return int(row["count_files"] or 0) + 1