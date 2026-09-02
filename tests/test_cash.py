from decimal import Decimal
import sqlite3
import unittest

from tests import test_fin1_import as fixtures
from warehouse.database import connect


class CashTests(unittest.TestCase):
    def test_credit_debit_cutoff_running_and_orphans(self):
        fixture=fixtures.ImportTests();fixture.setUp()
        try:
            c=sqlite3.connect(fixture.snapshot/'db.sqlite3')
            c.executescript("""
                ALTER TABLE fin1_conta ADD COLUMN saldo REAL;
                UPDATE fin1_conta SET saldo=14.34;
                ALTER TABLE fin1_lancamento ADD COLUMN dtliq TEXT;
                ALTER TABLE fin1_lancamento ADD COLUMN credito INTEGER;
                ALTER TABLE fin1_lancamento ADD COLUMN saldo REAL;
                UPDATE fin1_lancamento SET dtliq='2026-01-01',credito=1,saldo=12.34;
                INSERT INTO fin1_lancamento VALUES(2,1,'','',3,'2026-01-02',0,9.34);
                INSERT INTO fin1_lancamento VALUES(3,1,'','',5,'2027-01-01',1,14.34);
                INSERT INTO fin1_lancamento VALUES(4,NULL,'','',100,'2026-01-03',1,100);
            """);c.close()
            fixture.manifest();fixture.run_import()
            with connect(fixture.database) as db:
                actual=db.execute('SELECT reconstructed_balance,balance_at_cutoff,legacy_delta,sign_mismatch_count,future_count FROM portfolio.cash_check').fetchone()
                self.assertEqual(actual,(Decimal('14.34'),Decimal('9.34'),Decimal('0'),1,1))
                self.assertEqual(db.execute('SELECT reconstructed_running_balance FROM portfolio.cash_detail WHERE legacy_id=2').fetchone()[0],Decimal('9.34'))
                self.assertIsNone(db.execute('SELECT reconstructed_running_balance FROM portfolio.cash_detail WHERE legacy_id=4').fetchone()[0])
        finally:fixture.tearDown()

    def test_missing_credit_flag_does_not_become_zero(self):
        fixture=fixtures.ImportTests();fixture.setUp()
        try:
            fixture.run_import()
            with connect(fixture.database) as db:
                result=db.execute('SELECT reconstructed_balance,incomplete_count,balance_at_cutoff FROM portfolio.cash_check').fetchone()
                self.assertEqual(result,(None,1,None))
        finally:fixture.tearDown()
