"""Small SQLite job registry shared by CLI and UI."""

import sqlite3
from datetime import UTC, datetime
from pathlib import Path


class JobRegistry:
    """Persist job status without introducing a service dependency."""

    def __init__(self, database: str | Path):
        self.database = Path(database)
        self.database.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute(
                """CREATE TABLE IF NOT EXISTS jobs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source TEXT NOT NULL,
                    status TEXT NOT NULL,
                    provider TEXT,
                    model TEXT,
                    error TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )"""
            )

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.database)

    def create(self, source: str, provider: str, model: str) -> int:
        now = datetime.now(UTC).isoformat()
        with self._connect() as connection:
            cursor = connection.execute(
                "INSERT INTO jobs(source,status,provider,model,error,created_at,updated_at) "
                "VALUES(?,?,?,?,?,?,?)",
                (source, "queued", provider, model, None, now, now),
            )
            return int(cursor.lastrowid)

    def update(self, job_id: int, status: str, error: str | None = None) -> None:
        now = datetime.now(UTC).isoformat()
        with self._connect() as connection:
            connection.execute(
                "UPDATE jobs SET status=?, error=?, updated_at=? WHERE id=?",
                (status, error, now, job_id),
            )

    def get(self, job_id: int) -> dict | None:
        with self._connect() as connection:
            connection.row_factory = sqlite3.Row
            row = connection.execute(
                "SELECT * FROM jobs WHERE id=?", (job_id,)
            ).fetchone()
        return dict(row) if row else None
