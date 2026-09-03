from pathlib import Path
import tempfile
import unittest
from scripts.retention_plan import plan


class RetentionTests(unittest.TestCase):
    def test_preserves_active_and_unknown(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            backups = root/'backups'; backups.mkdir()
            releases = root/'releases'; releases.mkdir()
            active = releases/('a'*40); active.mkdir()
            other = releases/('b'*40); other.mkdir()
            for day in range(1, 10):
                snapshot = backups/f'202609{day:02d}T030000Z'
                (snapshot/'data').mkdir(parents=True)
                (snapshot/'data/fin2.duckdb').touch()
                (snapshot/'manifest.json').write_text('{}')
            (backups/'incomplete').mkdir()
            result = plan(backups, releases, active, versions=1)
            self.assertEqual(sum(r['action']=='candidate' for r in result), 2)
            self.assertTrue(all(r['action']=='keep' for r in result if r['path']==str(active)))
            self.assertTrue((backups/'20260901T030000Z').exists())

    def test_refuses_active_outside_release_root(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with self.assertRaises(ValueError):
                plan(root, root, root)
