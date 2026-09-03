from datetime import datetime, timezone
from decimal import Decimal
import json
import sqlite3
import unittest
from unittest.mock import patch

from fin2.portfolio.brapi import capture, parse_quote, validate_mapping, fetch
from fin2.portfolio.price_jobs import run as run_price_job
from tests import test_fin1_import as fixtures
from warehouse.database import connect

NOW = datetime(2026,8,31,20,tzinfo=timezone.utc)


def response(**overrides):
    data = {'currency':'BRL','regularMarketPrice':12.3456789012,'regularMarketTime':'2026-08-31T18:00:00Z'}
    data.update(overrides)
    return json.dumps({'results':[{'requestedSymbol':'PETR4','symbol':'PETR4','changed':False,'data':data}]}).encode()


class BrapiTests(unittest.TestCase):
    def test_invalid_quotes_fail_closed(self):
        self.assertEqual(parse_quote(response(),'PETR4',NOW)[0],Decimal('12.3456789012'))
        for body in (b'not json',b'{}',response(currency='USD'),response(regularMarketPrice=0),
                     response(regularMarketPrice=True),response(regularMarketPrice='NaN'),
                     response(regularMarketTime='2027-01-01T00:00:00Z'),response(regularMarketTime='2026-08-01'),
                     response().replace(b'false',b'true'),response().replace(b'PETR4',b'PETR3')):
            with self.subTest(body=body), self.assertRaises(ValueError):
                parse_quote(body,'PETR4',NOW)

    def test_snapshot_mapping_capture_rejection_and_dedup(self):
        f=fixtures.ImportTests();f.setUp()
        try:
            c=sqlite3.connect(f.snapshot/'db.sqlite3')
            c.executescript("""
                CREATE TABLE fin1_moeda(id INTEGER PRIMARY KEY,abrev TEXT);
                INSERT INTO fin1_moeda VALUES(1,'REAL');
                CREATE TABLE fin1_webscrap(id INTEGER PRIMARY KEY,plugin TEXT,multiplicador REAL);
                INSERT INTO fin1_webscrap VALUES(1,'atuBrAPI',1);
                CREATE TABLE fin1_ativo(id INTEGER PRIMARY KEY,abrev TEXT,moeda_id INTEGER,webscrap_id INTEGER,cotacao REAL);
                INSERT INTO fin1_ativo VALUES(1,'PETR4',1,1,9);
            """);c.close();f.manifest();f.run_import()
            with connect(f.database) as c:
                record=c.execute('SELECT source_record_id FROM market.asset_catalog').fetchone()[0]
                with self.assertRaises(ValueError):validate_mapping(c,record,'VALE3')
                first=capture(c,record,'PETR4',response(),NOW)
                self.assertEqual(first['status'],'accepted')
                self.assertTrue(capture(c,record,'PETR4',response(),NOW)['reused'])
                self.assertEqual(capture(c,record,'PETR4',response(currency='USD'),NOW)['status'],'rejected')
                self.assertEqual(c.execute('SELECT count(*) FROM market.quote_capture').fetchone()[0],2)
                self.assertEqual(c.execute("SELECT response_body FROM market.quote_capture WHERE status='accepted'").fetchone()[0],response())
                self.assertEqual(c.execute('SELECT legacy_price FROM portfolio.asset').fetchone()[0],9)
                self.assertEqual(c.execute("SELECT price FROM market.quote_capture WHERE status='rejected'").fetchone()[0],None)
                c.execute("UPDATE source_record SET payload=json_merge_patch(payload, '{\"multiplicador\":100}') WHERE table_name='fin1_webscrap'")
                with self.assertRaisesRegex(ValueError,'multiplicador 1'):
                    validate_mapping(c,record,'PETR4')
                c.execute("""INSERT INTO market.asset_provider_override
                  VALUES (?,'atuBrAPI','PETR4',1,'reviewed test mapping','{}',now())""",[record])
                validate_mapping(c,record,'PETR4')
            import os
            os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings')
            import django
            django.setup()
            from django.test import Client, override_settings
            with override_settings(WAREHOUSE_PATH=f.database, ALLOWED_HOSTS=['testserver']):
                client=Client()
                page=client.get('/fin2/cotacoes/')
                self.assertEqual(page.status_code,200)
                self.assertIn(b'PETR4',page.content)
                evidence=client.get(f"/fin2/cotacoes/{first['capture_id']}/resposta/")
                self.assertEqual(evidence.content,response())
                self.assertTrue(evidence['Content-Disposition'].startswith('attachment'))
                self.assertIn('no-store',evidence['Cache-Control'])
        finally:f.tearDown()

    @patch('fin2.portfolio.brapi.build_opener')
    def test_transport_failure_is_not_silently_imported(self, opener):
        from urllib.error import HTTPError
        opener.return_value.open.side_effect=HTTPError('https://brapi.dev',429,'limited',{},None)
        with self.assertRaisesRegex(ValueError,'HTTP 429'):
            fetch('PETR4')

    def test_background_job_persists_progress_and_capture(self):
        f=fixtures.ImportTests();f.setUp()
        try:
            c=sqlite3.connect(f.snapshot/'db.sqlite3')
            c.executescript("""
              CREATE TABLE fin1_moeda(id INTEGER PRIMARY KEY,abrev TEXT); INSERT INTO fin1_moeda VALUES(1,'REAL');
              CREATE TABLE fin1_webscrap(id INTEGER PRIMARY KEY,plugin TEXT,multiplicador REAL); INSERT INTO fin1_webscrap VALUES(1,'atuBrAPI',1);
              CREATE TABLE fin1_ativo(id INTEGER PRIMARY KEY,abrev TEXT,moeda_id INTEGER,webscrap_id INTEGER,cotacao REAL,dt_cotacao TEXT);
              INSERT INTO fin1_ativo VALUES(1,'PETR4',1,1,9,'2025-01-01');
              ALTER TABLE fin1_aplicacao ADD COLUMN ativo_id INTEGER; UPDATE fin1_aplicacao SET ativo_id=1;
            """);c.close();f.manifest();result=f.run_import();batch=result['batch_id']
            job='b'*64
            with connect(f.database) as db:
                db.execute("INSERT INTO price_update_job(job_id,batch_id,status,created_at,message) VALUES(?,?,'queued',?,'test')",[job,batch,NOW])
            def fake(symbols):
                self.assertEqual(symbols,['PETR4'])
                return response(),NOW
            run_price_job(f.database,job,batch,fetcher=fake)
            with connect(f.database) as db:
                state=db.execute('SELECT status,target_count,accepted_count,rejected_count,failed_count FROM price_update_job WHERE job_id=?',[job]).fetchone()
                self.assertEqual(state,('completed',1,1,0,0))
                self.assertEqual(db.execute('SELECT price FROM market.latest_external_price').fetchone()[0],Decimal('12.3456789012'))
                from fin2.dashboard.views import valuation_query
                sql,params=valuation_query({'analysis_cutoff':NOW.date(),'batch':{'batch_id':batch},'portfolio_filter':'','year_filter':''})
                selected=db.execute('SELECT legacy_price,price_source FROM ('+sql+") WHERE asset_id=1",params).fetchone()
                self.assertEqual(selected,(Decimal('12.3456789012'),'brapi_v2'))
        finally:f.tearDown()
