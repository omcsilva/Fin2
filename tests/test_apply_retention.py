import unittest
from scripts.apply_retention import apply
from tests import test_retention_plan
from scripts.retention_plan import plan


class ApplyRetentionTests(unittest.TestCase):
    def setUp(self):
        self.fixture = test_retention_plan.RetentionTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        f = self.fixture
        self.current = plan(f.backups, f.releases, f.active, f.previous, lambda n,d: True)
        self.removed = []

    def execute(self, approved, check=lambda c: True):
        f = self.fixture
        apply(approved, self.current, f.backups, f.releases, f.active, f.previous,
              check, self.removed.append)

    def test_only_verified_candidates(self):
        self.execute(self.current)
        self.assertEqual(set(self.removed), {self.fixture.first, self.fixture.old})

    def test_stale_approval_removes_nothing(self):
        with self.assertRaises(ValueError):
            self.execute(self.current[:-1])
        self.assertEqual(self.removed, [])

    def test_missing_git_commit_removes_nothing(self):
        with self.assertRaises(ValueError):
            self.execute(self.current, lambda c: False)
        self.assertEqual(self.removed, [])

    def test_active_release_cannot_be_removed(self):
        for row in self.current:
            if row['path'] == str(self.fixture.active): row['action'] = 'candidate'
        with self.assertRaises(ValueError):
            self.execute(self.current)
        self.assertEqual(self.removed, [])
