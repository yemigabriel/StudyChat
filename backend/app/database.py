import sqlite3
from pathlib import Path

from backend.app.config import Settings


def connect(settings: Settings) -> sqlite3.Connection:
    path = Path(settings.database_path)
    if str(path.parent) != ".":
        path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute(
        """CREATE TABLE IF NOT EXISTS inbound_messages (
            message_sid TEXT PRIMARY KEY,
            sender TEXT NOT NULL,
            body TEXT NOT NULL,
            received_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            reply_status TEXT NOT NULL DEFAULT 'pending'
        )"""
    )
    connection.execute(
        """CREATE TABLE IF NOT EXISTS telegram_updates (
            update_id INTEGER PRIMARY KEY,
            telegram_user_id TEXT NOT NULL,
            received_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )"""
    )
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS learners (
            learner_id TEXT PRIMARY KEY,
            sender TEXT NOT NULL UNIQUE,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS materials (
            material_id TEXT PRIMARY KEY,
            learner_id TEXT NOT NULL REFERENCES learners(learner_id),
            filename TEXT NOT NULL,
            source_type TEXT NOT NULL,
            status TEXT NOT NULL CHECK(status IN ('processing', 'ready', 'failed')),
            summary TEXT,
            error TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS source_chunks (
            chunk_id TEXT PRIMARY KEY,
            material_id TEXT NOT NULL REFERENCES materials(material_id),
            learner_id TEXT NOT NULL REFERENCES learners(learner_id),
            source_type TEXT NOT NULL,
            page_number INTEGER NOT NULL,
            text TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS source_chunks_material_idx ON source_chunks(material_id);
        CREATE TABLE IF NOT EXISTS telegram_study_state (
            telegram_user_id TEXT PRIMARY KEY,
            active_material_id TEXT,
            quiz_id TEXT,
            quiz_json TEXT,
            quiz_index INTEGER NOT NULL DEFAULT 0,
            quiz_score INTEGER NOT NULL DEFAULT 0,
            quiz_answered INTEGER NOT NULL DEFAULT 0,
            flashcards_id TEXT,
            flashcards_json TEXT,
            flashcard_index INTEGER NOT NULL DEFAULT 0,
            flashcard_revealed INTEGER NOT NULL DEFAULT 0
        );
        """
    )
    state_columns = {str(row[1]) for row in connection.execute("PRAGMA table_info(telegram_study_state)")}
    for column, definition in (
        ("flashcards_id", "TEXT"),
        ("flashcards_json", "TEXT"),
        ("flashcard_index", "INTEGER NOT NULL DEFAULT 0"),
        ("flashcard_revealed", "INTEGER NOT NULL DEFAULT 0"),
    ):
        if column not in state_columns:
            connection.execute(f"ALTER TABLE telegram_study_state ADD COLUMN {column} {definition}")
    connection.commit()
    return connection
