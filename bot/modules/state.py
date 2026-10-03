from __future__ import annotations

import sqlite3
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path


@dataclass
class MessageMemory:
    db_path: Path
    retention_days: int
    message_channels: dict[tuple[int, str], dict[int, datetime]] = field(
        default_factory=lambda: defaultdict(dict),
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
        self._connection.execute("PRAGMA journal_mode=WAL")
        self._connection.execute("PRAGMA foreign_keys=ON")
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
        now = datetime.now(tz=UTC)

        expired_channels = [
            ch
            for ch, ts in self.message_channels[key].items()
            if (now - ts).total_seconds() >= 60  # noqa: PLR2004
        ]
        for ch in expired_channels:
            del self.message_channels[key][ch]

        self.message_channels[key][channel_id] = now
        return len(self.message_channels[key])

    def close(self) -> None:
        self._connection.close()

    def _history_cutoff(self) -> datetime:
        return datetime.now(tz=UTC) - timedelta(days=self.retention_days)


class WhitelistedUsers:
    """Database to hold users that are entirely whitelisted from all detection and actions."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(self.db_path)
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS whitelist (
                user_id INTEGER PRIMARY KEY,
                expires_at INTEGER
            )
            """,
        )
        self._connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_whitelist_expires_at
            ON whitelist (expires_at)
            """,
        )
        self._connection.execute("PRAGMA journal_mode=WAL")
        self._connection.execute("PRAGMA foreign_keys=ON")
        self._connection.commit()

    def add_user(self, user_id: int, expires_at: datetime | None = None) -> None:
        # if self.is_whitelisted(user_id):
        #     return

        expires_ts = int(expires_at.timestamp()) if expires_at else None
        self._connection.execute(
            """
            INSERT INTO whitelist (user_id, expires_at)
            VALUES (?, ?)
            ON CONFLICT(user_id) DO UPDATE SET expires_at = excluded.expires_at
            """,
            (user_id, expires_ts),
        )
        self._connection.commit()

    def remove_user(self, user_id: int) -> None:
        self._connection.execute(
            "DELETE FROM whitelist WHERE user_id = ?",
            (user_id,),
        )
        self._connection.commit()

    def is_whitelisted(self, user_id: int) -> bool:
        now_ts = int(datetime.now(tz=UTC).timestamp())
        cursor = self._connection.execute(
            """
            SELECT 1 FROM whitelist
            WHERE user_id = ? AND (expires_at IS NULL OR expires_at > ?)
            LIMIT 1
            """,
            (user_id, now_ts),
        )
        return cursor.fetchone() is not None

    def remove_expired(self) -> None:
        now_ts = int(datetime.now(tz=UTC).timestamp())
        self._connection.execute(
            "DELETE FROM whitelist WHERE expires_at IS NOT NULL AND expires_at <= ?",
            (now_ts,),
        )
        self._connection.commit()

    def get_all_whitelisted_users(self) -> list[tuple[int, datetime | None]]:
        cursor = self._connection.execute("SELECT user_id, expires_at FROM whitelist")
        results = []
        for user_id, expires_ts in cursor.fetchall():
            expires_at = (
                datetime.fromtimestamp(expires_ts, tz=UTC) if expires_ts is not None else None
            )
            results.append((user_id, expires_at))
        return results

    def close(self) -> None:
        self._connection.close()
