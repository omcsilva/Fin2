import unittest
from fin2.imports import xp_reconciliation as xp
from .test_xp_statement import XPFlowTests

class XPResultadoTests(XPFlowTests):
    def test_resultado_counterparty_becomes_deposit(self):
        identifier = self.upload([['31/12/2023','Transferência','Credito','150,00','150,00']])
        xp.document(self.db, identifier)
        # Review as transfer but with RESULTADO
        xp.review(self.db, identifier, 1, self.decision(
            action='new', event_type='transfer', counterparty='RESULTADO', reason='From P&L'
        ))
        
        # Check if it was mutated
        item = xp._load(self.db_conn(), identifier, True)
        self.assertEqual(item['rows'][0]['decision']['event_type'], 'deposit')
        self.assertIsNone(item['rows'][0]['decision']['counterparty'])
        
        # Commit should create a deposit, not a transfer
        xp.commit(self.db, identifier)
        conn = self.db_conn()
        events = conn.execute('select event_type, amount, transfer_id from ledger.manual_event').fetchall()
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0][0], 'deposit')
        self.assertIsNone(events[0][2]) # transfer_id should be None

    def test_resultado_counterparty_becomes_withdrawal(self):
        identifier = self.upload([['31/12/2023','Transferência','Debito','-150,00','-150,00']])
        xp.document(self.db, identifier)
        xp.review(self.db, identifier, 1, self.decision(
            action='new', event_type='transfer', counterparty='RESULTADO', reason='To P&L'
        ))
        
        item = xp._load(self.db_conn(), identifier, True)
        self.assertEqual(item['rows'][0]['decision']['event_type'], 'withdrawal')
        
        xp.commit(self.db, identifier)
        conn = self.db_conn()
        events = conn.execute('select event_type, amount, transfer_id from ledger.manual_event').fetchall()
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0][0], 'withdrawal')

if __name__ == '__main__':
    unittest.main()
