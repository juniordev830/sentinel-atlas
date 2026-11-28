"""Persistência SQLite mínima para geofences locais."""

from __future__ import annotations

import os
import math
import sqlite3
from contextlib import closing
from pathlib import Path

from python.gps_core import Geofence, Position


# GPS deletion is OPT-IN. Never silently migrate or truncate existing databases.
# Configure a positive bound only after backing up the database.
def _retention_limit_from_environment() -> int | None:
    setting = os.getenv("SENTINEL_POSITION_RETENTION_LIMIT", "").strip()
    if not setting:
        return None
    if not setting.isascii() or not setting.isdecimal():
        raise ValueError("SENTINEL_POSITION_RETENTION_LIMIT must be an integer from 1 to 1000000")
    value = int(setting)
    if not 1 <= value <= 1_000_000:
        raise ValueError("SENTINEL_POSITION_RETENTION_LIMIT must be an integer from 1 to 1000000")
    return value


POSITION_RETENTION_LIMIT = _retention_limit_from_environment()


class GeofenceStore:
    def __init__(self, database_path: str | Path) -> None:
        self.path = Path(database_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as connection:
            with connection:
                connection.execute("""
                    CREATE TABLE IF NOT EXISTS geofences (
                        name TEXT PRIMARY KEY,
                        latitude REAL NOT NULL,
                        longitude REAL NOT NULL,
                        radius_meters REAL NOT NULL
                    )
                """)
                connection.execute("""
                    CREATE TABLE IF NOT EXISTS positions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        latitude REAL NOT NULL,
                        longitude REAL NOT NULL,
                        timestamp REAL NOT NULL
                    )
                """)
                connection.execute("""
                    CREATE INDEX IF NOT EXISTS idx_positions_timestamp_id
                    ON positions(timestamp DESC, id DESC)
                """)

                connection.execute("""
                    CREATE TABLE IF NOT EXISTS browser_sessions (
                        digest TEXT PRIMARY KEY,
                        expires_at INTEGER NOT NULL
                    )
                """)
                connection.execute("""
                    CREATE INDEX IF NOT EXISTS idx_browser_sessions_expiry
                    ON browser_sessions(expires_at)
                """)

    def create_session(self, digest: str, now: int, expires_at: int) -> bool:
        with closing(self._connect()) as connection, connection:
            connection.execute("DELETE FROM browser_sessions WHERE expires_at <= ?", (now,))
            cursor = connection.execute("""
                INSERT INTO browser_sessions (digest, expires_at)
                SELECT ?, ? WHERE (SELECT COUNT(*) FROM browser_sessions) < 4096
            """, (digest, expires_at))
            return cursor.rowcount == 1

    def session_valid(self, digest: str, now: int) -> bool:
        with closing(self._connect()) as connection:
            return connection.execute(
                "SELECT 1 FROM browser_sessions WHERE digest = ? AND expires_at > ?",
                (digest, now),
            ).fetchone() is not None

    def revoke_session(self, digest: str) -> None:
        with closing(self._connect()) as connection, connection:
            connection.execute("DELETE FROM browser_sessions WHERE digest = ?", (digest,))

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path)

    def save(self, fence: Geofence) -> None:
        with closing(self._connect()) as connection:
            with connection:
                connection.execute(
                    "INSERT OR REPLACE INTO geofences (name, latitude, longitude, radius_meters) VALUES (?, ?, ?, ?)",
                    (fence.name, fence.latitude, fence.longitude, fence.radius_meters),
                )

    def delete(self, name: str) -> bool:
        with closing(self._connect()) as connection:
            with connection:
                cursor = connection.execute(
                    "DELETE FROM geofences WHERE name = ?",
                    (name,),
                )
                return cursor.rowcount > 0

    def list(self) -> list[Geofence]:
        with closing(self._connect()) as connection:
            with connection:
                rows = connection.execute(
                    "SELECT name, latitude, longitude, radius_meters FROM geofences ORDER BY name"
                ).fetchall()
        return [Geofence(*row) for row in rows]

    def save_position(self, position: Position) -> None:
        with closing(self._connect()) as connection:
            with connection:
                connection.execute(
                    "INSERT INTO positions (latitude, longitude, timestamp) VALUES (?, ?, ?)",
                    (position.latitude, position.longitude, position.timestamp),
                )
                # Deletion is an explicit operator choice, never triggered by startup.
                # When opted in, it runs atomically only after a new GPS observation.
                if POSITION_RETENTION_LIMIT is not None:
                    connection.execute("""
                        DELETE FROM positions WHERE id NOT IN
                            (SELECT id FROM positions ORDER BY id DESC LIMIT ?)
                    """, (POSITION_RETENTION_LIMIT,))

    def list_positions(self, limit: int = 100, *, start: float | None = None,
                       end: float | None = None) -> list[Position]:
        """Consultas inclusivas por timestamp Unix; não alteram a retenção."""
        for value in (start, end):
            if value is not None and (not math.isfinite(value) or value < 0):
                raise ValueError("Timestamp inválido")
        if start is not None and end is not None and start > end:
            raise ValueError("O início não pode ser posterior ao fim")
        conditions, params = [], []
        if start is not None:
            conditions.append("timestamp >= ?")
            params.append(start)
        if end is not None:
            conditions.append("timestamp <= ?")
            params.append(end)
        where = " WHERE " + " AND ".join(conditions) if conditions else ""
        safe_limit = max(1, min(limit, 1000))
        params.append(safe_limit)
        with closing(self._connect()) as connection:
            rows = connection.execute(
                "SELECT latitude, longitude, timestamp FROM positions" + where +
                " ORDER BY timestamp DESC, id DESC LIMIT ?",
                params,
            ).fetchall()
        return [Position(*row) for row in rows]
