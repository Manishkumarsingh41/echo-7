from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
import uuid


@dataclass(frozen=True, slots=True)
class SavedChat:
    id: str
    title: str
    created_at: str
    updated_at: str


@dataclass(frozen=True, slots=True)
class SavedMessage:
    id: int
    chat_id: str
    role: str
    content: str
    created_at: str


class ChatHistoryStore:
    """Persistent local chat history for ECHO-7."""

    def __init__(self, database_path: Path | str | None = None) -> None:
        if database_path is None:
            data_dir = Path(__file__).resolve().parent.parent / "data"
            data_dir.mkdir(parents=True, exist_ok=True)
            database_path = data_dir / "echo_history.db"

        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)

        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS chats (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )

            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(chat_id)
                        REFERENCES chats(id)
                        ON DELETE CASCADE
                )
                """
            )

            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_messages_chat
                ON messages(chat_id, id)
                """
            )

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    def create_chat(self, title: str = "New Chat") -> str:
        chat_id = uuid.uuid4().hex
        now = self._now()

        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO chats (
                    id,
                    title,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?)
                """,
                (
                    chat_id,
                    title,
                    now,
                    now,
                ),
            )

        return chat_id

    def list_chats(self) -> list[SavedChat]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT id, title, created_at, updated_at
                FROM chats
                ORDER BY updated_at DESC
                """
            ).fetchall()

        return [
            SavedChat(
                id=row["id"],
                title=row["title"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )
            for row in rows
        ]

    def get_messages(self, chat_id: str) -> list[SavedMessage]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT
                    id,
                    chat_id,
                    role,
                    content,
                    created_at
                FROM messages
                WHERE chat_id = ?
                ORDER BY id ASC
                """,
                (chat_id,),
            ).fetchall()

        return [
            SavedMessage(
                id=row["id"],
                chat_id=row["chat_id"],
                role=row["role"],
                content=row["content"],
                created_at=row["created_at"],
            )
            for row in rows
        ]

    def add_message(
        self,
        chat_id: str,
        role: str,
        content: str,
    ) -> None:
        content = content.strip()

        if not content:
            return

        now = self._now()

        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO messages (
                    chat_id,
                    role,
                    content,
                    created_at
                )
                VALUES (?, ?, ?, ?)
                """,
                (
                    chat_id,
                    role,
                    content,
                    now,
                ),
            )

            connection.execute(
                """
                UPDATE chats
                SET updated_at = ?
                WHERE id = ?
                """,
                (
                    now,
                    chat_id,
                ),
            )

    def rename_chat(
        self,
        chat_id: str,
        title: str,
    ) -> None:
        title = title.strip()

        if not title:
            return

        with self._connect() as connection:
            connection.execute(
                """
                UPDATE chats
                SET title = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    title,
                    self._now(),
                    chat_id,
                ),
            )

    def auto_title_from_message(
        self,
        chat_id: str,
        message: str,
    ) -> str:
        cleaned = " ".join(message.strip().split())

        if not cleaned:
            title = "New Chat"
        elif len(cleaned) <= 38:
            title = cleaned
        else:
            title = cleaned[:38].rstrip() + "..."

        self.rename_chat(
            chat_id,
            title,
        )

        return title

    def delete_chat(self, chat_id: str) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                DELETE FROM messages
                WHERE chat_id = ?
                """,
                (chat_id,),
            )

            connection.execute(
                """
                DELETE FROM chats
                WHERE id = ?
                """,
                (chat_id,),
            )

    def chat_exists(self, chat_id: str) -> bool:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT 1
                FROM chats
                WHERE id = ?
                LIMIT 1
                """,
                (chat_id,),
            ).fetchone()

        return row is not None