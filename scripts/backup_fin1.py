"""Capture and verify Fin1 in a new private directory outside this repository."""

import argparse
import hashlib
import json
from pathlib import Path
import shlex
import sqlite3
import subprocess
import tarfile


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", required=True)
    parser.add_argument("--source", required=True)
    parser.add_argument("--destination", type=Path, required=True)
    args = parser.parse_args()
    repository = Path(__file__).resolve().parents[1]
    destination = args.destination.resolve()
    if destination.is_relative_to(repository):
        parser.error("Private data must remain outside the repository")
    if args.host.startswith("-"):
        parser.error("Invalid SSH host")
    destination.mkdir(parents=True, exist_ok=False)
    script = Path(__file__).with_name("fin1_snapshot_remote.py").read_bytes()
    archive_path = destination / "snapshot.tar"
    with archive_path.open("wb") as archive:
        subprocess.run(
            ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", args.host,
             "python3 - " + shlex.quote(args.source)],
            input=script, stdout=archive, check=True, timeout=300,
        )
    restore = destination / "restored"
    restore.mkdir()
    with tarfile.open(archive_path, "r:") as archive:
        members = archive.getmembers()
        if any(not member.isfile() for member in members):
            raise ValueError("Unexpected non-file archive member")
        archive.extractall(restore, members=members, filter="data")
    manifest = json.loads((restore / "manifest.json").read_text(encoding="utf-8"))
    actual = {path.relative_to(restore).as_posix() for path in restore.rglob("*") if path.is_file()}
    if actual != set(manifest["files"]) | {"manifest.json"}:
        raise ValueError("Snapshot inventory mismatch")
    for relative, metadata in manifest["files"].items():
        path = (restore / relative).resolve()
        if not path.is_relative_to(restore) or path.stat().st_size != metadata["bytes"] or digest(path) != metadata["sha256"]:
            raise ValueError("Snapshot file verification failed")
    for name, expected in manifest["databases"].items():
        connection = sqlite3.connect((restore / name).as_uri() + "?mode=ro", uri=True)
        try:
            if connection.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
                raise ValueError("Restored SQLite integrity check failed")
            if connection.execute("PRAGMA foreign_key_check").fetchall():
                raise ValueError("Restored SQLite foreign key check failed")
            for table, count in expected["table_counts"].items():
                sql = 'SELECT count(*) FROM "' + table.replace('"', '""') + '"'
                if connection.execute(sql).fetchone()[0] != count:
                    raise ValueError("Restored table count mismatch")
        finally:
            connection.close()
    result = {"verified": True, "files": len(manifest["files"]), "databases": len(manifest["databases"]),
              "archive_sha256": digest(archive_path), "consistency": manifest["consistency"]}
    (destination / "verification.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
