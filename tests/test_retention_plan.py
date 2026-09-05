from pathlib import Path
import tempfile
import unittest
from scripts.retention_plan import plan
from scripts.fin2_backup import backup

class RetentionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        root=Path(self.temp.name)
        self.backups=root/'backups';self.backups.mkdir()
        self.releases=root/'releases';self.releases.mkdir()
        self.active=self.releases/('a'*40);self.active.mkdir()
        self.previous=self.releases/('b'*40);self.previous.mkdir()
        self.old_release=self.releases/('c'*40);self.old_release.mkdir()
        source=root/'source';source.mkdir();(source/'fin2.duckdb').write_bytes(b'synthetic')
        self.regular=[];self.pre_updates=[]
        for index in range(9):
            item=self.backups/f'202609{index+1:02d}T030000Z';backup(source,item)
            (item/'external-copy.sha256').write_text('a'*64+'  fin2-'+item.name+'.tar.gz.gpg')
            self.regular.append(item)
        for index in range(5):
            item=self.backups/f'pre-update-202608{index+1:02d}T030000Z';backup(source,item)
            (item/'external-copy.sha256').write_text('a'*64+'  fin2-'+item.name+'.tar.gz.gpg')
            self.pre_updates.append(item)
        (self.regular[3]/'restore-validated').touch()

    def actions(self,check=lambda n,d:True):
        return {r['path']:r for r in plan(self.backups,self.releases,self.active,self.previous,check)}

    def test_keeps_seven_regular_three_preupdate_and_validated_reference(self):
        rows=self.actions()
        for item in self.regular[-7:]:self.assertEqual(rows[str(item)]['action'],'keep')
        self.assertEqual(rows[str(self.regular[0])]['action'],'candidate')
        self.assertEqual(rows[str(self.regular[1])]['action'],'candidate')
        self.assertEqual(rows[str(self.regular[3])]['action'],'keep')
        for item in self.pre_updates[-3:]:self.assertEqual(rows[str(item)]['action'],'keep')
        for item in self.pre_updates[:2]:self.assertEqual(rows[str(item)]['action'],'candidate')

    def test_keeps_active_and_previous_release(self):
        rows=self.actions()
        self.assertEqual(rows[str(self.active)]['action'],'keep')
        self.assertEqual(rows[str(self.previous)]['action'],'keep')
        self.assertEqual(rows[str(self.old_release)]['action'],'candidate')

    def test_missing_external_confirmation_blocks_old_backup(self):
        rows=self.actions(lambda n,d:False)
        self.assertEqual(rows[str(self.regular[0])]['action'],'keep')

    def test_refuses_active_outside_release_root(self):
        with self.assertRaises(ValueError):
            plan(self.backups,self.releases,self.backups)
