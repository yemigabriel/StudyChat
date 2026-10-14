import sqlite3
from pathlib import Path

from backend.app.config import Settings


def connect(settings: Settings) -> sqlite3.Connection:
    path = Path(settings.database_path)
    if str(path.parent) != ".":
        path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=10)
    connection.execute(
        """CREATE TABLE IF NOT EXISTS inbound_messages (
            message_sid TEXT PRIMARY KEY,
            sender TEXT NOT NULL,
            body TEXT NOT NULL,
            received_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            reply_status TEXT NOT NULL DEFAULT 'pending'
        )"""
    )
    connection.commit()
    return connection
