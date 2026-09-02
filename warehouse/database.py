"""Offline warehouse access. Do not run alongside a web database owner."""

from contextlib import contextmanager
import hashlib
from pathlib import Path
import threading

import duckdb

WRITE_LOCK = threading.RLock()
MIGRATIONS = Path(__file__).with_name("migrations")


@contextmanager
def connect(path):
    with WRITE_LOCK:
        connection = duckdb.connect(str(path), config={"memory_limit": "1GB", "threads": 2})
        try:
            yield connection
        finally:
            connection.close()


def migrate(connection, directory=MIGRATIONS):
    connection.execute("CREATE TABLE IF NOT EXISTS schema_migration (version VARCHAR PRIMARY KEY, sha256 VARCHAR NOT NULL)")
    applied = dict(connection.execute("SELECT version, sha256 FROM schema_migration").fetchall())
    files = sorted(directory.glob("*.sql"))
    available = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    if any(available.get(name) != sha for name, sha in applied.items()):
        raise ValueError("Applied migration is missing or its checksum changed")
    for path in files:
        if path.name in applied:
            continue
        if applied and path.name < max(applied):
            raise ValueError("Cannot insert a migration before an applied migration")
        connection.execute("BEGIN")
        try:
            connection.execute(path.read_text(encoding="utf-8"))
            connection.execute("INSERT INTO schema_migration VALUES (?, ?)", [path.name, available[path.name]])
            connection.execute("COMMIT")
        except Exception:
            connection.execute("ROLLBACK")
            raise
