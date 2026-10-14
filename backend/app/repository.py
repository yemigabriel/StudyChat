import sqlite3
import uuid
from collections.abc import Sequence

from backend.app.config import Settings
from backend.app.contracts import ChunkRecord
from backend.app.database import connect


def get_or_create_learner(settings: Settings, sender: str) -> str:
    learner_id = str(uuid.uuid4())
    with connect(settings) as db:
        db.execute("INSERT OR IGNORE INTO learners(learner_id, sender) VALUES (?, ?)", (learner_id, sender))
        row = db.execute("SELECT learner_id FROM learners WHERE sender=?", (sender,)).fetchone()
    return str(row[0])


def begin_material(
    settings: Settings,
    material_id: str,
    learner_id: str,
    filename: str,
    chunks: Sequence[ChunkRecord],
) -> bool:
    with connect(settings) as db:
        row = db.execute("SELECT status FROM materials WHERE material_id=?", (material_id,)).fetchone()
        if row and row[0] == "ready":
            return False
        db.execute(
            """INSERT INTO materials(material_id, learner_id, filename, source_type, status)
               VALUES (?, ?, ?, 'pdf', 'processing')
               ON CONFLICT(material_id) DO UPDATE SET status='processing', error=NULL""",
            (material_id, learner_id, filename),
        )
        db.execute("DELETE FROM source_chunks WHERE material_id=?", (material_id,))
        db.executemany(
            """INSERT INTO source_chunks(chunk_id, material_id, learner_id, source_type, page_number, text)
               VALUES (?, ?, ?, ?, ?, ?)""",
            [
                (c.chunk_id, c.material_id, c.learner_id, c.source_type, c.page_number, c.text)
                for c in chunks
            ],
        )
        return True


def mark_material_ready(settings: Settings, material_id: str, summary: str) -> None:
    with connect(settings) as db:
        db.execute(
            "UPDATE materials SET status='ready', summary=?, error=NULL WHERE material_id=?",
            (summary, material_id),
        )


def mark_material_failed(settings: Settings, material_id: str, reason: str) -> None:
    with connect(settings) as db:
        db.execute(
            "UPDATE materials SET status='failed', error=? WHERE material_id=? AND status!='ready'",
            (reason[:500], material_id),
        )


def material_status(settings: Settings, material_id: str) -> str | None:
    with connect(settings) as db:
        row = db.execute("SELECT status FROM materials WHERE material_id=?", (material_id,)).fetchone()
    return str(row[0]) if row else None


def get_material_summary(settings: Settings, material_id: str) -> str | None:
    with connect(settings) as db:
        row = db.execute("SELECT summary FROM materials WHERE material_id=? AND status='ready'", (material_id,)).fetchone()
    return str(row[0]) if row and row[0] is not None else None


def ready_chunks_by_ids(settings: Settings, learner_id: str, chunk_ids: Sequence[str]) -> list[dict[str, object]]:
    if not chunk_ids:
        return []
    placeholders = ",".join("?" for _ in chunk_ids)
    with connect(settings) as db:
        rows = db.execute(
            f"""SELECT c.chunk_id, c.material_id, c.learner_id, c.source_type, c.page_number, c.text
                FROM source_chunks AS c JOIN materials AS m ON m.material_id=c.material_id
                WHERE c.learner_id=? AND m.learner_id=? AND m.status='ready'
                  AND c.chunk_id IN ({placeholders})""",
            [learner_id, learner_id, *chunk_ids],
        ).fetchall()
    return [dict(row) for row in rows]
