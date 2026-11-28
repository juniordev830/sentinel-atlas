"""Atomic limits for workers that use the same local SQLite database."""
from contextlib import closing
from pathlib import Path
import sqlite3
import time
from uuid import uuid4


class SharedLimits:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as connection, connection:
            connection.execute("""
                CREATE TABLE IF NOT EXISTS login_limits (
                    client TEXT NOT NULL, window INTEGER NOT NULL, attempts INTEGER NOT NULL,
                    PRIMARY KEY (window, client)
                )
            """)
            connection.execute("""
                CREATE TABLE IF NOT EXISTS limit_leases (
                    id TEXT PRIMARY KEY, kind TEXT NOT NULL, expires_at REAL NOT NULL
                )
            """)
            connection.execute("""
                CREATE INDEX IF NOT EXISTS idx_limit_leases_kind_expiry
                ON limit_leases(kind, expires_at)
            """)

    def _connect(self):
        return sqlite3.connect(self.path, timeout=1)

    def allow_login(self, client: str, window: int, per_client: int, total: int) -> bool:
        with closing(self._connect()) as connection, connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute("DELETE FROM login_limits WHERE window < ?", (window,))
            count, aggregate = connection.execute("""
                SELECT COALESCE(SUM(CASE WHEN client = ? THEN attempts ELSE 0 END), 0),
                       COALESCE(SUM(attempts), 0)
                FROM login_limits WHERE window = ?
            """, (client, window)).fetchone()
            if count >= per_client or aggregate >= total:
                return False
            connection.execute("""
                INSERT INTO login_limits (client, window, attempts) VALUES (?, ?, 1)
                ON CONFLICT (window, client) DO UPDATE SET attempts = attempts + 1
            """, (client, window))
            return True

    def acquire(self, kind: str, maximum: int, ttl: float, *, now: float | None = None) -> str | None:
        now = time.time() if now is None else now
        lease = uuid4().hex
        with closing(self._connect()) as connection, connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute("DELETE FROM limit_leases WHERE kind = ? AND expires_at <= ?", (kind, now))
            cursor = connection.execute("""
                INSERT INTO limit_leases (id, kind, expires_at)
                SELECT ?, ?, ? WHERE (SELECT COUNT(*) FROM limit_leases WHERE kind = ?) < ?
            """, (lease, kind, now + ttl, kind, maximum))
            return lease if cursor.rowcount == 1 else None

    def renew(self, lease: str, ttl: float, *, now: float | None = None) -> bool:
        now = time.time() if now is None else now
        with closing(self._connect()) as connection, connection:
            return connection.execute("""
                UPDATE limit_leases SET expires_at = ? WHERE id = ? AND expires_at > ?
            """, (now + ttl, lease, now)).rowcount == 1

    def release(self, lease: str) -> None:
        with closing(self._connect()) as connection, connection:
            connection.execute("DELETE FROM limit_leases WHERE id = ?", (lease,))
