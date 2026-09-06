from datetime import date
from decimal import Decimal
import unittest
import os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

from tests import test_fin1_import as fixtures
from warehouse.database import connect
from fin2.portfolio.manual_ledger import create, correct, reverse


class ResultAccountTests(unittest.TestCase):
    def test_purchase_funding_reinvestment_and_reversals(self):
        f = fixtures.ImportTests()
        f.setUp()
        try:
            f.run_import()
            with connect(f.database) as db:
                account, application = db.execute('''SELECT a.source_record_id,p.source_record_id
                    FROM portfolio.account a JOIN portfolio.application p
                    ON p.batch_id=a.batch_id AND p.account_id=a.legacy_id LIMIT 1''').fetchone()
                opening = db.execute('SELECT coalesce(sum(amount),0) FROM ledger.investment_cash_entry').fetchone()[0]
                from fin2.dashboard.views import valuation_query
                batch = db.execute('SELECT batch_id FROM import_batch').fetchone()[0]
                sql, params = valuation_query(dict(batch=dict(batch_id=batch),
                    analysis_cutoff=date(2026,9,5), year_filter='', portfolio_filter=''))
                def quantity():
                    return db.execute('SELECT quantity_at_cutoff FROM ('+sql+') v WHERE source_record_id=?',
                                      [*params,application]).fetchone()[0]
                initial_quantity = quantity()
            def event(kind, amount, **kwargs):
                return create(f.database, account_record=account, application_record=application,
                    event_type=kind, amount=amount, settlement_date='2026-09-05', currency='BRL',
                    description='Teste Conta de Resultado', **kwargs)
            purchase = event('buy', -1000, quantity=10, request_key='e'*32)
            self.assertEqual(purchase, event('buy', -1000, quantity=10, request_key='e'*32))
            event('income', 100)
            event('sell', 200, quantity=2)
            event('buy', -50, quantity=1, funding_source='dividends')
            event('buy', -100, quantity=1, funding_source='sales')
            event('buy', -50, quantity=1, funding_source='portability')
            with connect(f.database) as db:
                self.assertEqual(db.execute('SELECT sum(amount) FROM ledger.purchase_contribution').fetchone()[0], Decimal(1000))
                self.assertEqual(db.execute('SELECT sum(amount) FROM ledger.investment_cash_entry').fetchone()[0]-opening, Decimal(100))
                self.assertEqual(db.execute('SELECT count(*) FROM ledger.purchase_funding').fetchone()[0], 4)
                self.assertEqual(quantity(), initial_quantity + 11)
            replacement = correct(f.database,purchase,settlement_date='2026-09-05',
                amount=-1100,quantity=11,description='Correção compra')
            with connect(f.database) as db:
                self.assertEqual(db.execute('SELECT sum(amount) FROM ledger.purchase_contribution WHERE reversed_at IS NULL').fetchone()[0], Decimal(1100))
                self.assertEqual(db.execute('SELECT sum(amount) FROM ledger.investment_cash_entry').fetchone()[0]-opening, Decimal(100))
            reverse(f.database,replacement)
            with connect(f.database) as db:
                self.assertEqual(db.execute('SELECT count(*) FROM ledger.purchase_contribution WHERE reversed_at IS NULL').fetchone()[0], 0)
                self.assertEqual(db.execute('SELECT sum(amount) FROM ledger.investment_cash_entry').fetchone()[0]-opening, Decimal(100))
                self.assertEqual(quantity(), initial_quantity + 1)
            with self.assertRaisesRegex(ValueError, 'Origem'):
                event('buy', -10, quantity=1, funding_source='invalid')
        finally:
            f.tearDown()
