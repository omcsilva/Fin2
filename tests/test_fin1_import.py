from datetime import date
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from fin2.imports.fin1 import digest, import_snapshot
from warehouse.database import connect, migrate


class ImportTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.snapshot = self.root / "snapshot"
        self.snapshot.mkdir()
        self.database = self.root / "output" / "fin2.duckdb"
        for name in ("db.sqlite3", "dados.sqlite3", "docs.sqlite3"):
            c = sqlite3.connect(self.snapshot / name)
            if name == "db.sqlite3":
                c.executescript("""
                    CREATE TABLE fin1_conta(id INTEGER PRIMARY KEY, abrev TEXT);
                    INSERT INTO fin1_conta VALUES(1,'TEST');
                    CREATE TABLE fin1_lancamento(id INTEGER PRIMARY KEY, conta_id INTEGER, nota_sinacor TEXT, nota_corretora TEXT, valor REAL);
                    INSERT INTO fin1_lancamento VALUES(1,1,'note.pdf','',12.34);
                    CREATE TABLE fin1_aplicacao(id INTEGER PRIMARY KEY, conta_id INTEGER);
                    INSERT INTO fin1_aplicacao VALUES(1,1);
                    CREATE TABLE fin1_movimentacao(id INTEGER PRIMARY KEY, aplicacao_id INTEGER, lancamento_id INTEGER, dtliq TEXT, dtmov TEXT);
                    INSERT INTO fin1_movimentacao VALUES(1,1,1,NULL,'2027-01-01');
                """)
            elif name == "docs.sqlite3":
                c.executescript("CREATE TABLE fin1_doc(id INTEGER PRIMARY KEY, item TEXT, texto TEXT); INSERT INTO fin1_doc VALUES(1,'/fin1/','<p>synthetic</p>');")
            c.close()
        attachment = self.snapshot / "ANEXOS" / "TEST" / "note.pdf"
        attachment.parent.mkdir(parents=True)
        attachment.write_bytes(b"synthetic fixture, not a renderable PDF")
        self.manifest()

    def tearDown(self):
        self.temporary.cleanup()

    def manifest(self):
        databases = {}
        for name in ("db.sqlite3", "dados.sqlite3", "docs.sqlite3"):
            c = sqlite3.connect(self.snapshot / name)
            tables = [r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")]
            databases[name] = {"table_counts": {t: c.execute('SELECT count(*) FROM "'+t+'"').fetchone()[0] for t in tables}}
            c.close()
        files = {p.relative_to(self.snapshot).as_posix(): {"sha256": digest(p), "bytes": p.stat().st_size}
                 for p in self.snapshot.rglob("*") if p.is_file() and p.name != "manifest.json"}
        (self.snapshot / "manifest.json").write_text(json.dumps({"format":1,"files":files,"databases":databases}), encoding="utf-8")

    def run_import(self):
        return import_snapshot(self.snapshot, self.database, date(2026,8,31))

    def test_links_payload_and_repeat_import(self):
        first = self.run_import()
        second = self.run_import()
        self.assertFalse(first["reused"])
        self.assertTrue(second["reused"])
        self.assertEqual(first["source_record"], 5)
        self.assertEqual(first["document_record_link"], 2)
        self.assertEqual(first["issues_by_code"], {"future_movement":1,"unsettled_movement":1})
        with connect(self.database) as c:
            self.assertEqual(c.execute("SELECT count(*) FROM import_batch").fetchone()[0],1)
            payload = json.loads(c.execute("SELECT payload FROM source_record WHERE table_name='fin1_lancamento'").fetchone()[0])
            self.assertEqual(payload["valor"],12.34)
            self.assertEqual(json.loads(c.execute("SELECT payload FROM source_record WHERE table_name='fin1_doc'").fetchone()[0])["texto"],"<p>synthetic</p>")

    def test_changed_attachment_is_rejected(self):
        self.run_import()
        (self.snapshot / "ANEXOS/TEST/note.pdf").write_bytes(b"changed")
        with self.assertRaisesRegex(ValueError,"verification failed"):
            self.run_import()
        with connect(self.database) as c:
            self.assertEqual(c.execute("SELECT count(*) FROM import_batch").fetchone()[0],1)

    def test_account_mismatch_does_not_inherit_document(self):
        c = sqlite3.connect(self.snapshot / "db.sqlite3")
        c.executescript("INSERT INTO fin1_conta VALUES(2,'OTHER'); UPDATE fin1_aplicacao SET conta_id=2;")
        c.close()
        self.manifest()
        result = self.run_import()
        self.assertEqual(result["document_record_link"],1)
        self.assertEqual(result["issues_by_code"]["account_mismatch"],1)

    def test_manifest_cannot_escape_snapshot(self):
        path = self.snapshot / "manifest.json"
        manifest = json.loads(path.read_text())
        manifest["files"]["../outside.pdf"] = {"bytes":0,"sha256":"invalid"}
        path.write_text(json.dumps(manifest),encoding="utf-8")
        with self.assertRaisesRegex(ValueError,"Unsafe source path"):
            self.run_import()
        self.assertFalse(self.database.exists())

    def test_failed_batch_rolls_back_records(self):
        c = sqlite3.connect(self.snapshot / "docs.sqlite3")
        c.executescript("CREATE TABLE fin1_invalid(id TEXT); INSERT INTO fin1_invalid VALUES('not-an-integer');")
        c.close()
        self.manifest()
        with self.assertRaises(ValueError):
            self.run_import()
        with connect(self.database) as c:
            self.assertEqual(c.execute("SELECT count(*) FROM import_batch").fetchone()[0],0)
            self.assertEqual(c.execute("SELECT count(*) FROM source_record").fetchone()[0],0)

    def test_applied_migration_cannot_change(self):
        directory = self.root / "migrations"
        directory.mkdir()
        migration = directory / "0001.sql"
        migration.write_text("CREATE TABLE example(id INTEGER);", encoding="utf-8")
        with connect(self.root / "test.duckdb") as c:
            migrate(c,directory)
            migration.write_text("CREATE TABLE changed(id INTEGER);", encoding="utf-8")
            with self.assertRaisesRegex(ValueError,"checksum changed"):
                migrate(c,directory)


if __name__ == "__main__":
    unittest.main()
