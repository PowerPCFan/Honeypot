import sqlite3
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path


@dataclass
class MessageMemory:
    db_path: Path
    retention_days: int
    message_channels: dict[tuple[int, str], set[int]] = field(
        default_factory=lambda: defaultdict(set),
    )

    def __post_init__(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(self.db_path)
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS message_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                message_id INTEGER NOT NULL UNIQUE,
                channel_id INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                is_clean INTEGER NOT NULL
            )
            """,
        )
        self._connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_message_history_user_clean_time "
            "ON message_history (user_id, is_clean, created_at)",
        )
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS honeypot_caught_users (
                user_id INTEGER PRIMARY KEY,
                caught_at TEXT NOT NULL
            )
            """,
        )
        self._connection.commit()
        self.purge_old_messages()

    @staticmethod
    def normalize_content(content: str) -> str:
        return " ".join(content.casefold().split())

    def clean_count_for(self, user_id: int) -> int:
        cutoff = self._history_cutoff().isoformat()
        cursor = self._connection.execute(
            """
            SELECT COUNT(*)
            FROM message_history
            WHERE user_id = ? AND is_clean = 1 AND created_at >= ?
            """,
            (user_id, cutoff),
        )
        return int(cursor.fetchone()[0])

    def record_message(
        self,
        *,
        user_id: int,
        message_id: int,
        channel_id: int,
        created_at: datetime,
        is_clean: bool,
    ) -> None:
        self._connection.execute(
            """
            INSERT OR IGNORE INTO message_history (
                user_id,
                message_id,
                channel_id,
                created_at,
                is_clean
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                user_id,
                message_id,
                channel_id,
                created_at.astimezone(UTC).isoformat(),
                int(is_clean),
            ),
        )
        self._connection.commit()
        self.purge_old_messages()

    def mark_honeypot_caught(self, user_id: int) -> None:
        self._connection.execute(
            """
            INSERT OR REPLACE INTO honeypot_caught_users (user_id, caught_at)
            VALUES (?, ?)
            """,
            (user_id, datetime.now(tz=UTC).isoformat()),
        )
        self._connection.commit()

    def was_honeypot_caught(self, user_id: int) -> bool:
        cursor = self._connection.execute(
            "SELECT 1 FROM honeypot_caught_users WHERE user_id = ? LIMIT 1",
            (user_id,),
        )
        return cursor.fetchone() is not None

    def purge_old_messages(self) -> None:
        self._connection.execute(
            "DELETE FROM message_history WHERE created_at < ?",
            (self._history_cutoff().isoformat(),),
        )
        self._connection.commit()

    def record_and_count_channels(self, user_id: int, content: str, channel_id: int) -> int:
        normalized = self.normalize_content(content)
        if not normalized:
            return 0

        key = (user_id, normalized)
        self.message_channels[key].add(channel_id)
        return len(self.message_channels[key])

    def close(self) -> None:
        self._connection.close()

    def _history_cutoff(self) -> datetime:
        return datetime.now(tz=UTC) - timedelta(days=self.retention_days)
