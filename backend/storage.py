"""Persistência SQLite mínima para geofences locais."""

from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path

from python.gps_core import Geofence, Position


# Retain only the most recent GPS observations to bound disk usage and exposure.
POSITION_RETENTION_LIMIT = 10_000


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
                # Also migrate existing installations on startup, not only new writes.
                connection.execute("""
                    DELETE FROM positions WHERE id NOT IN
                        (SELECT id FROM positions ORDER BY id DESC LIMIT ?)
                """, (POSITION_RETENTION_LIMIT,))

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
                connection.execute("""
                    DELETE FROM positions WHERE id NOT IN
                        (SELECT id FROM positions ORDER BY id DESC LIMIT ?)
                """, (POSITION_RETENTION_LIMIT,))

    def list_positions(self, limit: int = 100) -> list[Position]:
        safe_limit = max(1, min(limit, 1000))
        with closing(self._connect()) as connection:
            rows = connection.execute(
                "SELECT latitude, longitude, timestamp FROM positions ORDER BY timestamp DESC, id DESC LIMIT ?",
                (safe_limit,),
            ).fetchall()
        return [Position(*row) for row in rows]
