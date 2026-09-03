import tempfile
import unittest
from pathlib import Path
from scripts.fin2_backup import backup, restore, verify


class BackupTests(unittest.TestCase):
    def test_roundtrip_and_corruption(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / 'source'
            source.mkdir()
            (source / 'fin2.duckdb').write_bytes(b'synthetic database')
            (source / 'catalog-images').mkdir()
            (source / 'catalog-images' / 'photo').write_bytes(b'photo')
            backup(source, root / 'backup')
            restore(root / 'backup', root / 'restored')
            self.assertEqual((root / 'restored/catalog-images/photo').read_bytes(), b'photo')
            with self.assertRaises(ValueError):
                restore(root / 'backup', source)
            (root / 'backup/data/fin2.duckdb').write_bytes(b'corrupted')
            with self.assertRaises(ValueError):
                verify(root / 'backup')

    def test_reject_nested_backup(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with self.assertRaises(ValueError):
                backup(root, root / 'backups')
