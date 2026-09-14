"""SQLite persistence for NETRA events and camera metadata."""

from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class EventStore:
    """Thread-safe local event store with a small, stable SQLite schema."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._connection = sqlite3.connect(str(self.path), check_same_thread=False)
        self._connection.row_factory = sqlite3.Row
        self._initialize()

    def _initialize(self) -> None:
        with self._lock, self._connection:
            self._connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS events (
                    event_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    camera_id TEXT NOT NULL,
                    location TEXT,
                    event_type TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    score INTEGER NOT NULL,
                    confidence REAL,
                    distance_m REAL,
                    track_id INTEGER,
                    evidence_path TEXT,
                    status TEXT NOT NULL DEFAULT 'ACTIVE',
                    metadata_json TEXT NOT NULL DEFAULT '{}'
                );
                CREATE INDEX IF NOT EXISTS idx_events_created_at ON events(created_at);
                CREATE INDEX IF NOT EXISTS idx_events_camera_id ON events(camera_id);
                CREATE INDEX IF NOT EXISTS idx_events_status ON events(status);
                
                CREATE TABLE IF NOT EXISTS users (
                    username TEXT PRIMARY KEY,
                    password TEXT NOT NULL,
                    role TEXT NOT NULL
                );
                
                CREATE TABLE IF NOT EXISTS login_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL,
                    login_time TEXT NOT NULL,
                    role TEXT NOT NULL
                );
                """
            )
            # Insert default users if they don't exist
            self._connection.execute(
                "INSERT OR IGNORE INTO users (username, password, role) VALUES (?, ?, ?)",
                ("admin", "admin", "admin")
            )
            self._connection.execute(
                "INSERT OR IGNORE INTO users (username, password, role) VALUES (?, ?, ?)",
                ("viewer", "viewer", "viewer")
            )

    def add_event(self, event: dict[str, Any]) -> str:
        event_id = str(event.get("event_id") or uuid.uuid4())
        created_at = str(event.get("created_at") or datetime.now(timezone.utc).isoformat())
        metadata = event.get("metadata", {})
        with self._lock, self._connection:
            self._connection.execute(
                """
                INSERT INTO events (
                    event_id, created_at, camera_id, location, event_type,
                    severity, score, confidence, distance_m, track_id,
                    evidence_path, status, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event_id,
                    created_at,
                    str(event.get("camera_id", "UNKNOWN")),
                    str(event.get("location", "")),
                    str(event.get("event_type", "SYSTEM_ERROR")),
                    str(event.get("severity", "WARNING")),
                    int(event.get("score", 0)),
                    event.get("confidence"),
                    event.get("distance_m"),
                    event.get("track_id"),
                    event.get("evidence_path"),
                    str(event.get("status", "ACTIVE")),
                    json.dumps(metadata),
                ),
            )
        return event_id

    def list_events(self, limit: int = 100) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._connection.execute(
                "SELECT * FROM events ORDER BY created_at DESC LIMIT ?", (max(1, limit),)
            ).fetchall()
        return [dict(row) for row in rows]

    def update_status(self, event_id: str, status: str) -> None:
        with self._lock, self._connection:
            self._connection.execute(
                "UPDATE events SET status = ? WHERE event_id = ?", (status, event_id)
            )

    def delete_event(self, event_id: str) -> None:
        with self._lock, self._connection:
            self._connection.execute(
                "DELETE FROM events WHERE event_id = ?", (event_id,)
            )

    def clear_events(self) -> None:
        with self._lock, self._connection:
            self._connection.execute("DELETE FROM events")

    def authenticate_user(self, username, password):
        with self._lock:
            row = self._connection.execute(
                "SELECT role FROM users WHERE username = ? AND password = ?", (username, password)
            ).fetchone()
            return row["role"] if row else None

    def log_login(self, username, role):
        login_time = datetime.now(timezone.utc).isoformat()
        with self._lock, self._connection:
            self._connection.execute(
                "INSERT INTO login_records (username, login_time, role) VALUES (?, ?, ?)",
                (username, login_time, role)
            )

    def get_login_records(self, limit=100):
        with self._lock:
            rows = self._connection.execute(
                "SELECT * FROM login_records ORDER BY login_time DESC LIMIT ?", (max(1, limit),)
            ).fetchall()
        return [dict(row) for row in rows]

    def close(self) -> None:
        with self._lock:
            self._connection.close()
