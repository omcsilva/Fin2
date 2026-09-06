from datetime import date,timedelta
from decimal import Decimal
from uuid import uuid4
import unittest
from django.test import Client,override_settings
from tests import test_report_status as status_fixtures
from fin2.portfolio.manual_prices import create
from fin2.portfolio.manual_ledger import create as create_event
from fin2.dashboard.views import valuation_query
from warehouse.database import connect


class ManualPriceTests(unittest.TestCase):
    def setUp(self):
        self.f=status_fixtures.ReportStatusTests();self.f.setUp()
    def tearDown(self):self.f.tearDown()
    def add(self,**kwargs):
        values=dict(asset_record=self.f.asset['record_id'],price='12.3456789012',currency='BRL',
            reference_date='2024-01-15',source='Avaliação própria',request_key=uuid4().hex)
        values.update(kwargs)
        return create(self.f.f.database,**values)
    def test_validation_audit_and_idempotency(self):
        key=uuid4().hex
        ident=self.add(request_key=key)
        self.assertEqual(self.add(request_key=key),ident)
        with connect(self.f.f.database) as db:
            self.assertEqual(db.execute('SELECT price FROM market.manual_price WHERE price_id=?',[ident]).fetchone()[0],Decimal('12.3456789012'))
            self.assertEqual(db.execute('SELECT count(*) FROM ledger.audit_log WHERE entity_id=?',[ident]).fetchone()[0],1)
        for fields in [dict(price='0'),dict(price='NaN'),dict(price='-1'),dict(price='1e99'),dict(currency='USD'),
                       dict(reference_date=str(date.today()+timedelta(days=1))),dict(source=''),dict(document_id='unknown')]:
            with self.subTest(fields=fields),self.assertRaises(ValueError):self.add(**fields)
    def test_as_of_price_correction_and_position_value(self):
        create_event(self.f.f.database,account_record=self.f.account['record_id'],application_record=self.f.application['record_id'],
            event_type='buy',quantity=2,amount=-20,currency='BRL',settlement_date='2024-01-01',description='Compra')
        self.add(price='10')
        self.add(price='11')
        self.add(price='20',reference_date='2025-01-15')
        with connect(self.f.f.database) as db:
            # A same-day external quote with an intraday timestamp must not
            # override a manual correction recorded later for that date.
            db.execute('''INSERT INTO market.asset_price_query_success VALUES
                (?,'brapi_v2',TIMESTAMPTZ '2024-01-15 22:00:00+00',
                 TIMESTAMPTZ '2024-01-15 20:00:00+00',99,'BRL','test-capture')''',
                [self.f.asset['record_id']])
            for cutoff,expected in [(date(2024,12,31),Decimal(11)),(date(2025,12,31),Decimal(20))]:
                data=dict(batch={'batch_id':self.f.batch},analysis_cutoff=cutoff,portfolio_filter='',year_filter=str(cutoff.year))
                sql,params=valuation_query(data)
                row=db.execute('SELECT legacy_price,reference_value,price_source FROM ('+sql+') v WHERE source_record_id=?',[*params,self.f.application['record_id']]).fetchone()
                self.assertEqual(row,(expected,expected*2,'manual'))
            data['historical']=True
            sql,params=valuation_query(data)
            row=db.execute('SELECT price_source FROM ('+sql+') v WHERE source_record_id=?',[*params,self.f.application['record_id']]).fetchone()
            self.assertEqual(row[0],'fin1_snapshot')
            self.assertEqual(db.execute('SELECT count(*) FROM market.manual_price').fetchone()[0],3)
    def test_form_csrf_write_permission_and_price_display(self):
        with override_settings(WAREHOUSE_PATH=self.f.f.database,ALLOWED_HOSTS=['testserver'],WRITE_ENABLED=True):
            client=Client(enforce_csrf_checks=True)
            response=client.get('/fin2/cotacoes/manuais/')
            self.assertEqual(response.status_code,200)
            fields=dict(asset=self.f.asset['record_id'],price='42',currency='BRL',reference_date=str(date.today()),source='Fonte de teste',request_key=uuid4().hex)
            self.assertEqual(client.post('/fin2/cotacoes/manuais/',fields).status_code,403)
            fields['csrfmiddlewaretoken']=client.cookies['csrftoken'].value
            self.assertEqual(client.post('/fin2/cotacoes/manuais/',fields).status_code,302)
            self.assertIn('Fonte de teste',client.get('/fin2/cotacoes/manuais/').content.decode())
            self.assertIn('R$ 42,00',client.get('/fin2/cotacoes/').content.decode())
            with override_settings(WRITE_ENABLED=False):
                self.assertEqual(client.post('/fin2/cotacoes/manuais/',fields).status_code,403)
