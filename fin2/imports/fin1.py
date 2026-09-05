"""Import verified Fin1 snapshots into an audit layer, without financial rewrites."""

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import sqlite3
import tempfile
from datetime import date

from warehouse.database import connect, migrate

DATABASES = ("db.sqlite3", "dados.sqlite3", "docs.sqlite3")
REPOSITORY = Path(__file__).resolve().parents[2]


def encode(value):
    # JSON preserves SQLite integer/real distinctions as Python int/float.
    # No Decimal or date coercion is performed in this audit layer.
    return json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False)


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def identity(*parts):
    return hashlib.sha256(encode(parts).encode()).hexdigest()


def safe_path(root, relative):
    part = PurePosixPath(relative)
    if part.is_absolute() or ".." in part.parts or "\\" in relative or ":" in relative:
        raise ValueError("Unsafe source path")
    path = (root / relative).resolve()
    if not path.is_relative_to(root):
        raise ValueError("Source path escapes snapshot")
    return path


def verify(snapshot):
    manifest = json.loads((snapshot / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("format") != 1 or not set(DATABASES).issubset(manifest["files"]):
        raise ValueError("Unsupported or incomplete manifest")
    for relative, metadata in manifest["files"].items():
        path = safe_path(snapshot, relative)
        if not path.is_file() or path.stat().st_size != metadata["bytes"] or digest(path) != metadata["sha256"]:
            raise ValueError("Snapshot verification failed: " + relative)
    return manifest


def store_document(source, storage, sha):
    key = sha[:2] + "/" + sha
    destination = safe_path(storage, key)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        if digest(destination) != sha:
            raise ValueError("Document storage corruption detected")
        return key
    descriptor, temporary = tempfile.mkstemp(dir=destination.parent, prefix="pending-")
    try:
        with os.fdopen(descriptor, "wb") as output, source.open("rb") as original:
            shutil.copyfileobj(original, output)
        if digest(Path(temporary)) != sha:
            raise ValueError("Document changed while copying")
        os.replace(temporary, destination)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return key


def summary(connection, batch_id, reused=False):
    result = {"batch_id": batch_id, "reused": reused}
    for table in ("source_record", "source_document", "import_issue"):
        result[table] = connection.execute(f"SELECT count(*) FROM {table} WHERE batch_id=?", [batch_id]).fetchone()[0]
    result["document_record_link"] = connection.execute(
        "SELECT count(*) FROM document_record_link l JOIN source_document d USING(document_id) WHERE d.batch_id=?", [batch_id]
    ).fetchone()[0]
    result["issues_by_code"] = dict(connection.execute(
        "SELECT code, count(*) FROM import_issue WHERE batch_id=? GROUP BY code ORDER BY code", [batch_id]
    ).fetchall())
    return result


def import_snapshot(snapshot, database, as_of):
    snapshot, database = Path(snapshot).resolve(), Path(database).resolve()
    if database.is_relative_to(REPOSITORY) or database.is_relative_to(snapshot):
        raise ValueError("Destination must be outside repository and source snapshot")
    manifest = verify(snapshot)
    batch = identity(manifest["files"])
    database.parent.mkdir(parents=True, exist_ok=True)
    storage = database.parent / "documents"
    storage.mkdir(exist_ok=True)
    with connect(database) as connection:
        migrate(connection)
        existing = connection.execute("SELECT as_of_date FROM import_batch WHERE batch_id=?", [batch]).fetchone()
        if existing:
            if existing[0] != as_of:
                raise ValueError("Existing batch has another review date; do not silently change its audit")
            for key, sha in connection.execute("SELECT storage_key, sha256 FROM source_document WHERE batch_id=?", [batch]).fetchall():
                if digest(safe_path(storage, key)) != sha:
                    raise ValueError("Stored document verification failed")
            return summary(connection, batch, True)
        connection.execute("BEGIN")
        try:
            connection.execute("INSERT INTO import_batch(batch_id,source_manifest,as_of_date) VALUES (?,?,?)", [batch, encode(manifest), as_of])
            records = {}
            for name in DATABASES:
                source = sqlite3.connect((snapshot / name).as_uri() + "?mode=ro", uri=True)
                source.row_factory = sqlite3.Row
                try:
                    source.execute("PRAGMA query_only=ON")
                    source.execute("BEGIN")
                    tables = [r[0] for r in source.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'fin1_%' ORDER BY name")]
                    expected = manifest["databases"][name]["table_counts"]
                    if set(tables) != set(expected):
                        raise ValueError("Source table inventory mismatch")
                    for table in tables:
                        quoted = '"' + table.replace('"', '""') + '"'
                        rows = [dict(r) for r in source.execute("SELECT * FROM " + quoted)]
                        if len(rows) != expected[table]:
                            raise ValueError("Source row count mismatch")
                        columns = [dict(r) for r in source.execute("PRAGMA table_info(" + quoted + ")")]
                        connection.execute("INSERT INTO source_table VALUES (?,?,?,?,?)", [batch, name, table, encode(columns), len(rows)])
                        records[(name, table)] = {}
                        for row in rows:
                            legacy_id = int(row["id"])
                            records[(name, table)][legacy_id] = row
                            connection.execute("INSERT INTO source_record VALUES (?,?,?,?,?,?)", [identity(batch,name,table,legacy_id), batch, name, table, legacy_id, encode(row)])
                finally:
                    source.close()
            documents = {}
            for relative, metadata in manifest["files"].items():
                if not relative.startswith("ANEXOS/"):
                    continue
                document_id = identity(batch, relative)
                key = store_document(safe_path(snapshot, relative), storage, metadata["sha256"])
                documents[relative] = document_id
                connection.execute("INSERT INTO source_document VALUES (?,?,?,?,?,?,?)", [document_id,batch,relative,PurePosixPath(relative).name,metadata["sha256"],metadata["bytes"],key])

            def record_id(table, identifier):
                return identity(batch, "db.sqlite3", "fin1_" + table, identifier)

            def issue(code, table=None, identifier=None, **details):
                rid = record_id(table, identifier) if table else None
                connection.execute("INSERT INTO import_issue VALUES (?,?,?,?,?)", [identity(batch,code,rid,details),batch,code,rid,encode(details)])

            def link(relative, table, identifier, relation):
                if relative not in documents:
                    issue("missing_document", table, identifier, path=relative, relation=relation)
                    return
                connection.execute("INSERT INTO document_record_link VALUES (?,?,?) ON CONFLICT DO NOTHING", [documents[relative],record_id(table,identifier),relation])

            def rows(table):
                return records.get(("db.sqlite3", "fin1_" + table), {})

            accounts, entries, holdings = rows("conta"), rows("lancamento"), rows("aplicacao")
            for identifier, row in entries.items():
                account = accounts.get(row.get("conta_id"))
                if not account:
                    issue("cash_without_account", "lancamento", identifier)
                for field in ("nota_sinacor", "nota_corretora"):
                    if row.get(field) and account:
                        link("ANEXOS/" + account["abrev"] + "/" + row[field], "lancamento", identifier, field)
            for identifier, row in rows("ativo").items():
                if row.get("pdf"):
                    link("ANEXOS/" + row["pdf"], "ativo", identifier, "asset_pdf")
            for identifier, row in rows("movimentacao").items():
                entry = entries.get(row.get("lancamento_id"))
                holding = holdings.get(row.get("aplicacao_id"))
                if not entry:
                    issue("movement_without_cash", "movimentacao", identifier)
                elif not holding or holding.get("conta_id") != entry.get("conta_id"):
                    issue("account_mismatch", "movimentacao", identifier, cash_id=entry["id"])
                else:
                    account = accounts.get(entry.get("conta_id"))
                    for field in ("nota_sinacor", "nota_corretora"):
                        if entry.get(field) and account:
                            link("ANEXOS/" + account["abrev"] + "/" + entry[field], "movimentacao", identifier, "via_cash_" + field)
                if row.get("dtliq") is None:
                    issue("unsettled_movement", "movimentacao", identifier)
                if any(str(row.get(field) or "")[:10] > as_of.isoformat() for field in ("dtmov", "dtliq")):
                    issue("future_movement", "movimentacao", identifier)
            for relative, document_id in documents.items():
                if not connection.execute("SELECT 1 FROM document_record_link WHERE document_id=? LIMIT 1", [document_id]).fetchone():
                    issue("unclassified_document", path=relative)
            connection.execute("""INSERT INTO market.asset_price_update_method(source_record_id,method)
              SELECT record_id,'BRAPI' FROM source_record
              WHERE batch_id=? AND database_name='db.sqlite3' AND table_name='fin1_ativo'
              ON CONFLICT DO NOTHING""",[batch])
            # A source changed during import must never produce a committed batch.
            if verify(snapshot) != manifest:
                raise ValueError("Manifest changed during import")
            connection.execute("COMMIT")
        except Exception:
            connection.execute("ROLLBACK")
            raise
        return summary(connection, batch)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--as-of", type=date.fromisoformat, required=True)
    args = parser.parse_args()
    print(encode(import_snapshot(args.snapshot, args.database, args.as_of)))


if __name__ == "__main__":
    main()
