import os
from pathlib import Path
from decimal import Decimal
import unittest
from unittest.mock import patch

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django
django.setup()
from django.test import Client, override_settings

from tests import test_fin1_import as fixtures
from warehouse.database import connect
from fin2.dashboard.views import _average_cost, _xirr


class DashboardTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.ImportTests()
        self.fixture.setUp()
        self.fixture.run_import()
        self.settings = override_settings(WAREHOUSE_PATH=self.fixture.database,
            DOCUMENT_ROOT=self.fixture.database.parent / "documents", ALLOWED_HOSTS=["testserver"])
        self.settings.enable()
        self.client = Client(enforce_csrf_checks=True)
        with connect(self.fixture.database) as c:
            self.document = c.execute("SELECT document_id FROM source_document").fetchone()[0]
            self.record = c.execute("SELECT record_id FROM source_record WHERE table_name='fin1_doc'").fetchone()[0]

    def tearDown(self):
        self.settings.disable()
        self.fixture.tearDown()

    def test_pages_and_escaped_legacy_html(self):
        for path in ("/fin2/", "/fin2/posicoes/", "/fin2/caixa/", "/fin2/caixa/?account=1", "/fin2/alocacao/", "/fin2/historico/", "/fin2/relatorios/", "/fin2/conciliacao/", "/fin2/registros/", "/fin2/documentos/", "/fin2/revisao/", f"/fin2/documentos/{self.document}/"):
            response = self.client.get(path)
            self.assertEqual(response.status_code,200,path)
            self.assertIn("no-store",response["Cache-Control"])
        positions = self.client.get('/fin2/posicoes/')
        self.assertIn('<th colspan="3">Total</th>',positions.content.decode())
        self.assertIn('aplicações',positions.content.decode())
        response = self.client.get(f"/fin2/registros/{self.record}/")
        self.assertContainsEscaped(response.content.decode())

    def test_overview_is_financial_and_keeps_currencies_separate(self):
        response=self.client.get('/fin2/')
        html=response.content.decode()
        self.assertIn('PATRIMÔNIO / VISÃO CONSOLIDADA',html)
        self.assertIn('Moedas não são somadas nem convertidas',html)
        self.assertIn('Conta de Resultado',html)
        self.assertIn('Resultado acumulado',html)
        self.assertIn('Total investido',html)
        self.assertIn('Total sacado',html)
        self.assertIn('<summary>Histórico</summary>',html)
        self.assertNotIn('<h2>Integridade da migração</h2>',html)

    def test_fin2_cash_includes_manual_events_and_archive_excludes_them(self):
        from datetime import date
        from fin2.portfolio.manual_ledger import create
        with connect(self.fixture.database) as c:
            account = c.execute('SELECT source_record_id FROM portfolio.account LIMIT 1').fetchone()[0]
        create(self.fixture.database,account_record=account,event_type='deposit',
               settlement_date=date.today(),currency='BRL',amount='123.45',
               description='Aporte exclusivo do ledger Fin2')
        current = self.client.get('/fin2/caixa/')
        self.assertEqual(current.status_code,200)
        self.assertIn('Aporte exclusivo do ledger Fin2',current.content.decode())
        self.assertNotIn('<th class="number">Saldo Fin1</th>',current.content.decode())
        for path in ('','posicoes/','caixa/','alocacao/','relatorios/','cotacoes/'):
            archived = self.client.get('/fin2/historico/fin1/'+path)
            self.assertEqual(archived.status_code,200,path)
            self.assertIn('Histórico · Fin1',archived.content.decode())
            self.assertNotIn('Aporte exclusivo do ledger Fin2',archived.content.decode())

    def test_reports_distinguish_market_return_from_portfolio_return(self):
        response=self.client.get('/fin2/relatorios/')
        html=response.content.decode()
        self.assertEqual(response.status_code,200)
        self.assertIn('Rendimentos e fluxo de caixa',html)
        self.assertIn('não representa ainda a rentabilidade pessoal da carteira',html)

    def test_reconciliation_compares_fin2_with_frozen_fin1_cutoff(self):
        response=self.client.get('/fin2/conciliacao/')
        html=response.content.decode()
        self.assertEqual(response.status_code,200)
        self.assertIn('Fechamento Fin2 × Fin1',html)
        self.assertIn('Avaliações',html)
        self.assertIn('Rendimentos',html)
        self.assertIn('Saldos por conta',html)
        self.assertIn('Fluxos por classificação',html)

    def test_xirr_for_one_year_gain(self):
        from datetime import date
        rate=_xirr([(date(2023,1,1),-100),(date(2024,1,1),110)])
        self.assertAlmostEqual(rate,.10,places=6)

    def test_current_account_excludes_transfers_and_dates_reversals(self):
        from datetime import date
        from fin2.portfolio.current_account import summarize
        with connect(self.fixture.database) as c:
            account, batch = c.execute('SELECT source_record_id,batch_id FROM portfolio.account LIMIT 1').fetchone()
            for identifier, kind, amount, day, reversal, transfer in [
                ('aporte', 'deposit', 1000, '2024-01-01', None, None),
                ('saque', 'withdrawal', -300, '2024-01-02', None, None),
                ('estorno', 'deposit', 300, '2024-02-01', 'saque', None),
                ('interna', 'deposit', 900, '2024-01-01', None, 'transfer')]:
                c.execute('''INSERT INTO ledger.manual_event
                    (event_id,account_source_record_id,event_type,settlement_date,currency,
                     amount,description,reverses_event_id,transfer_id)
                    VALUES (?,?,?,?,?,?,?,?,?)''',
                    [identifier, account, kind, day, 'EUR', amount, identifier, reversal, transfer])
            positions = [dict(currency='EUR', valuation_status='priced', reference_value=Decimal(900))]
            january = next(r for r in summarize(c,batch,date(2024,1,31),positions) if r['currency']=='EUR')
            february = next(r for r in summarize(c,batch,date(2024,2,28),positions) if r['currency']=='EUR')
            self.assertEqual(january['result'], Decimal(200))
            self.assertEqual(february['result'], Decimal(-100))
        response = self.client.get('/fin2/relatorios/')
        self.assertEqual(response.status_code, 200)
        self.assertIn('Conta de Resultado', response.content.decode())

    def test_moving_average_cost_and_realized_gain(self):
        from datetime import date
        events=[{'event_date':date(2024,1,1),'operation':'Compra','quantity':10,'amount':101,'gross_amount':100,'allocated_cash':True},
                {'event_date':date(2024,2,1),'operation':'Compra','quantity':10,'amount':202,'gross_amount':200,'allocated_cash':True},
                {'event_date':date(2024,3,1),'operation':'Venda','quantity':5,'amount':99,'gross_amount':100,'allocated_cash':True}]
        result=_average_cost(events,date(2024,12,31),2024)
        self.assertEqual(result['status'],'calculated')
        self.assertEqual(result['quantity'],Decimal('15'))
        self.assertEqual(result['average_cost'],Decimal('15.15'))
        self.assertEqual(result['realized_gain'],Decimal('23.25'))
        self.assertEqual(result['allocated_expenses'],Decimal('4'))
        self.assertEqual(result['sale_details'][0]['proceeds'],Decimal('99'))

    def assertContainsEscaped(self, html):
        self.assertIn("&lt;p&gt;synthetic&lt;/p&gt;",html)
        self.assertNotIn("<p>synthetic</p>",html)

    def test_unsupported_content_download_only(self):
        response = self.client.get(f"/fin2/documentos/{self.document}/arquivo/")
        self.assertEqual(response.status_code,200)
        self.assertTrue(response["Content-Disposition"].startswith("attachment"))
        self.assertIn("sandbox",response["Content-Security-Policy"])
        self.assertEqual(b"".join(response.streaming_content),b"synthetic fixture, not a renderable PDF")
        response.close()

    def test_invalid_resource_and_filters(self):
        self.assertEqual(self.client.get('/fin2/cotacoes/').status_code,200)
        captures=self.client.get('/fin2/cotacoes/capturas/')
        self.assertEqual(captures.status_code,200)
        self.assertIn('Cobertura completa',captures.content.decode())
        coverage=self.client.get('/fin2/cotacoes/')
        self.assertIn('Capturas externas',coverage.content.decode())
        self.assertEqual(self.client.get('/fin2/cotacoes/', {'provider':"';DROP TABLE source_record;--",'q':'<script>'}).status_code,200)
        self.assertEqual(self.client.get('/fin2/cotacoes/?batch=invalid').status_code,404)
        self.assertEqual(self.client.get("/fin2/documentos/invalid/").status_code,404)
        self.assertEqual(self.client.get("/fin2/?batch=invalid").status_code,404)
        self.assertEqual(self.client.get("/fin2/registros/", {"table":"';DROP TABLE source_record;--"}).status_code,200)
        self.assertEqual(self.client.get("/fin2/registros/?page=99999999999999999").status_code,200)
        for path in ('/fin2/posicoes/','/fin2/alocacao/','/fin2/cotacoes/'):
            response=self.client.get(path,{'sort':"name; DROP TABLE source_record;--",'dir':'sideways'})
            self.assertEqual(response.status_code,200)

    def test_financial_tables_expose_server_controls(self):
        for path,table in (('/fin2/posicoes/','positions'),('/fin2/alocacao/','allocation'),('/fin2/cotacoes/','prices')):
            response=self.client.get(path,{'sort':'asset','dir':'desc','q':'TEST'})
            html=response.content.decode()
            self.assertEqual(response.status_code,200)
            self.assertIn(f'data-table-controls="{table}"',html)
            self.assertIn('name="dir" value="desc"',html)

    def test_menu_groups_keep_all_destinations(self):
        html=self.client.get('/fin2/').content.decode()
        for group in ('Carteira','Movimentações','Dados e auditoria'):
            self.assertIn(f'<summary>{group}</summary>',html)
        for path in ('posicoes','alocacao','historico','relatorios','caixa','lancamentos','importar','conciliacao',
                     'cotacoes','registros','documentos','revisao'):
            self.assertIn(f'/fin2/{path}/',html)

    def test_quantity_detail_and_invalid_account(self):
        with connect(self.fixture.database) as c:
            application=c.execute("SELECT source_record_id FROM portfolio.application LIMIT 1").fetchone()[0]
        self.assertEqual(self.client.get(f'/fin2/posicoes/{application}/').status_code,200)
        self.assertEqual(self.client.get(f'/fin2/posicoes/{self.record}/').status_code,404)
        self.assertEqual(self.client.get('/fin2/caixa/?account=999').status_code,404)

    def test_missing_database_is_not_created(self):
        absent = self.fixture.root / "absent.duckdb"
        with override_settings(WAREHOUSE_PATH=absent):
            self.assertEqual(self.client.get("/fin2/").status_code,503)
        self.assertFalse(absent.exists())

    def test_no_post_without_csrf(self):
        self.assertEqual(self.client.post("/fin2/").status_code,403)
        self.assertEqual(self.client.post('/fin2/cotacoes/atualizar/').status_code,403)
        self.assertEqual(self.client.post('/fin2/cotacoes/atualizar/cancelar/').status_code,403)
        self.assertEqual(self.client.post('/fin2/relatorios/fluxos/invalid/classificar/').status_code,403)

    def test_cash_flow_decision_validates_identifier(self):
        self.client.get('/fin2/relatorios/')
        token=self.client.cookies['csrftoken'].value
        response=self.client.post('/fin2/relatorios/fluxos/invalid/classificar/',{
          'csrfmiddlewaretoken':token,'category':'income','rationale':'Conferido no documento'})
        self.assertEqual(response.status_code,400)

    @patch('fin2.dashboard.views.cancel_price_job',return_value=('a'*64,True))
    @patch('fin2.dashboard.views.create_price_job',return_value=('a'*64,True))
    def test_background_price_job_start_and_status(self, create_job, cancel_job):
        page=self.client.get('/fin2/')
        self.assertIn('Atualizar preços',page.content.decode())
        self.assertIn('/fin2/cotacoes/atualizar/cancelar/',page.content.decode())
        token=self.client.cookies['csrftoken'].value
        response=self.client.post('/fin2/cotacoes/atualizar/',{'csrfmiddlewaretoken':token})
        self.assertEqual(response.status_code,202)
        self.assertTrue(response.json()['created'])
        create_job.assert_called_once()
        cancelled=self.client.post('/fin2/cotacoes/atualizar/cancelar/',{'csrfmiddlewaretoken':token})
        self.assertEqual(cancelled.status_code,200)
        self.assertTrue(cancelled.json()['cancelled'])
        cancel_job.assert_called_once()
        status=self.client.get('/fin2/cotacoes/atualizacao/')
        self.assertEqual(status.status_code,200)
        self.assertEqual(status.json()['status'],'idle')

    def test_storage_path_cannot_escape_and_corruption_not_served(self):
        with connect(self.fixture.database) as c:
            key = c.execute("SELECT storage_key FROM source_document").fetchone()[0]
        (self.fixture.database.parent / "documents" / key).write_bytes(b"corrupt")
        self.assertEqual(self.client.get(f"/fin2/documentos/{self.document}/arquivo/").status_code,404)
        with connect(self.fixture.database) as c:
            c.execute("UPDATE source_document SET storage_key='../db.sqlite3'")
        self.assertEqual(self.client.get(f"/fin2/documentos/{self.document}/arquivo/").status_code,404)


if __name__ == "__main__":
    unittest.main()
