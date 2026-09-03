from datetime import date
from decimal import Decimal
from pathlib import Path
import unittest

from fin2.portfolio.manual_ledger import create
from tests import test_fin1_import as fixtures
from warehouse.database import connect


class ManualLedgerTests(unittest.TestCase):
    def test_validated_atomic_event_and_audit(self):
        f=fixtures.ImportTests();f.setUp()
        try:
            f.run_import()
            with connect(f.database) as c:
                account=c.execute('select source_record_id from portfolio.account').fetchone()[0]
            event=create(f.database,account_record=account,event_type='deposit',
                         settlement_date=date(2026,8,31),currency='brl',amount='12.34567',
                         description='  aporte   manual ')
            with connect(f.database) as c:
                self.assertEqual(c.execute('select amount,currency,description from ledger.manual_event where event_id=?',[event]).fetchone(),(Decimal('12.3457'),'BRL','aporte manual'))
                self.assertEqual(c.execute('select action from ledger.audit_log where entity_id=?',[event]).fetchone()[0],'create')
            with self.assertRaisesRegex(ValueError,'Conta desconhecida'):
                create(f.database,account_record='missing',event_type='deposit',settlement_date='2026-08-31',currency='BRL',amount=1,description='x')
        finally: f.tearDown()


if __name__=='__main__': unittest.main()
