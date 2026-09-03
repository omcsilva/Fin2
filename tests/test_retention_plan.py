from pathlib import Path
import tempfile
import unittest
from scripts.retention_plan import plan
from scripts.fin2_backup import backup


class RetentionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.backups = root/'backups'; self.backups.mkdir()
        self.releases = root/'releases'; self.releases.mkdir()
        self.active = self.releases/('a'*40); self.active.mkdir()
        self.previous = self.releases/('b'*40); self.previous.mkdir()
        self.old = self.releases/('c'*40); self.old.mkdir()
        source = root/'source'; source.mkdir()
        (source/'fin2.duckdb').write_bytes(b'synthetic database')
        self.first = self.backups/'20260901T030000Z'
        self.last = self.backups/'pre-update-20260902T030000Z'
        for target in (self.first, self.last): backup(source, target)
        (self.first/'external-copy.sha256').write_text('a'*64+'  fin2-'+self.first.name+'.tar.gz.gpg')

    def test_keeps_latest_and_active_previous(self):
        result = plan(self.backups,self.releases,self.active,self.previous,lambda n,d: True)
        actions = {r['path']: r['action'] for r in result}
        for item in (self.active,self.previous,self.last): self.assertEqual(actions[str(item)],'keep')
        for item in (self.first,self.old): self.assertEqual(actions[str(item)],'candidate')
        self.assertTrue(self.first.exists())

    def test_missing_external_confirmation_blocks_backup_candidates(self):
        for callback in (None, lambda n,d: False):
            result = plan(self.backups,self.releases,self.active,external_check=callback)
            self.assertTrue(all(r['action']=='keep' for r in result))

    def test_missing_receipt_blocks_removal_even_if_remote_available(self):
        (self.first/'external-copy.sha256').unlink()
        result = plan(self.backups,self.releases,self.active,self.previous,lambda n,d: True)
        self.assertEqual(next(r['action'] for r in result if r['path']==str(self.first)),'keep')

    def test_corrupt_newest_does_not_displace_valid_backup(self):
        (self.last/'data/fin2.duckdb').write_bytes(b'corrupted')
        result = plan(self.backups,self.releases,self.active,self.previous,lambda n,d: True)
        self.assertTrue(all(r['action']=='keep' for r in result if r['path'].startswith(str(self.backups))))

    def test_refuses_active_outside_release_root(self):
        with self.assertRaises(ValueError): plan(self.backups,self.releases,self.backups)
