"""Read-only source capture; run through SSH with Python's standard library.

Writes only to a private temporary directory, removed on exit. Emits a tar
archive on stdout only after source stability and SQLite checks succeed.
"""

import hashlib
import json
from pathlib import Path
import shutil
import sqlite3
import sys
import tarfile
import tempfile
from datetime import datetime, timezone


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def source_inventory(root):
    paths = [root / name for name in ("db.sqlite3", "dados.sqlite3", "docs.sqlite3")]
    paths.extend(p for p in (root / "ANEXOS").rglob("*") if p.is_file())
    paths.extend(p for p in root.glob("*.sqlite3-*") if p.is_file())
    result = {}
    for path in sorted(paths):
        if path.is_symlink() or not path.resolve().is_relative_to(root):
            raise ValueError("Source file escapes the selected root")
        before = path.stat()
        sha = digest(path)
        after = path.stat()
        if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
            raise RuntimeError("Source changed during hashing; retry during a quiet interval")
        result[path.relative_to(root).as_posix()] = {
            "bytes": after.st_size, "mtime_ns": after.st_mtime_ns, "sha256": sha
        }
    return result


def main():
    root = Path(sys.argv[1]).resolve(strict=True)
    started = datetime.now(timezone.utc).isoformat()
    baseline = source_inventory(root)
    with tempfile.TemporaryDirectory(prefix="fin2-snapshot-") as temporary:
        target = Path(temporary)
        databases = {}
        for name in ("db.sqlite3", "dados.sqlite3", "docs.sqlite3"):
            source = sqlite3.connect((root / name).as_uri() + "?mode=ro", uri=True)
            destination = sqlite3.connect(target / name)
            try:
                source.execute("PRAGMA query_only=ON")
                source.backup(destination)
                integrity = destination.execute("PRAGMA integrity_check").fetchall()
                foreign_keys = destination.execute("PRAGMA foreign_key_check").fetchall()
                if integrity != [("ok",)] or foreign_keys:
                    raise RuntimeError("Database verification failed: " + name)
                tables = [row[0] for row in destination.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'fin1_%' ORDER BY name"
                )]
                databases[name] = {
                    "integrity": "ok", "foreign_key_violations": 0,
                    "table_counts": {table: destination.execute(
                        'SELECT count(*) FROM "' + table.replace('"', '""') + '"'
                    ).fetchone()[0] for table in tables},
                }
            finally:
                destination.close()
                source.close()
        for relative, metadata in baseline.items():
            if not relative.startswith("ANEXOS/"):
                continue
            path = target / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(root / relative, path)
            if digest(path) != metadata["sha256"]:
                raise RuntimeError("Attachment changed during copy")
        if source_inventory(root) != baseline:
            raise RuntimeError("Source changed during capture; no snapshot delivered")
        files = {
            path.relative_to(target).as_posix(): {"bytes": path.stat().st_size, "sha256": digest(path)}
            for path in sorted(target.rglob("*")) if path.is_file()
        }
        manifest = {
            "format": 1, "started_utc": started,
            "completed_utc": datetime.now(timezone.utc).isoformat(),
            "source_root": str(root), "method": "SQLite online backup + attachment copy",
            "consistency": "Source hashes and metadata unchanged across capture; not a coordinated application-level freeze",
            "files": files, "databases": databases,
        }
        (target / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        with tarfile.open(fileobj=sys.stdout.buffer, mode="w|") as archive:
            for path in sorted(target.rglob("*")):
                if path.is_file():
                    archive.add(path, arcname=path.relative_to(target).as_posix(), recursive=False)


if __name__ == "__main__":
    main()
