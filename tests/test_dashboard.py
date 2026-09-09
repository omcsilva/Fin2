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
from fin2.dashboard.views import _average_cost, _tax_class, _xirr


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

    def test_account_detail_and_menu_links(self):
        with connect(self.fixture.database) as c:
            account_id = c.execute('SELECT legacy_id FROM portfolio.account LIMIT 1').fetchone()[0]
            application = c.execute('SELECT source_record_id FROM portfolio.application WHERE account_id=? LIMIT 1', [account_id]).fetchone()[0]
        response = self.client.get(f'/fin2/contas/{account_id}/?account=999999&tab=aplicacoes')
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn('<h2>Aplicações</h2>', html)
        self.assertIn('<strong>Saldo no corte:</strong>', html)
        self.assertNotIn('tab=saldos', html)
        self.assertNotIn('<h2>Extrato do ledger</h2>', html)
        for tab, heading in [('movimentacoes', 'Extrato do ledger')]:
            response = self.client.get(f'/fin2/contas/{account_id}/?tab={tab}')
            self.assertEqual(response.status_code, 200)
            self.assertIn(f'<h2>{heading}</h2>', response.content.decode())
            self.assertNotIn('<h2>Aplicações</h2>', response.content.decode())
        self.assertIn(f'/fin2/posicoes/{application}/', html)
        self.assertIn(f'/fin2/contas/{account_id}/?', html)
        self.assertEqual(self.client.get('/fin2/contas/999999/').status_code, 404)
        self.assertEqual(self.client.get('/fin2/contas/invalida/').status_code, 404)

    def test_account_result_sums_remaining_cost_and_flags_missing_prices(self):
        from datetime import date
        from fin2.dashboard.ledger_views import summarize_application_results
        positions = [dict(legacy_id=1, quantity_at_cutoff=Decimal(5),
                          reference_value=Decimal(80), valuation_status='priced'),
                     dict(legacy_id=2, quantity_at_cutoff=Decimal(1),
                          reference_value=None, valuation_status='missing_price')]
        events = [dict(application_id=1, event_date=date(2024,1,1), operation='buy',
                       quantity=Decimal(10), amount=Decimal(100)),
                  dict(application_id=1, event_date=date(2024,2,1), operation='sell',
                       quantity=Decimal(5), amount=Decimal(70)),
                  dict(application_id=2, event_date=date(2024,1,1), operation='buy',
                       quantity=Decimal(1), amount=Decimal(20))]
        result = summarize_application_results(positions, events, date(2024,12,31))
        self.assertEqual(result['invested'], Decimal(50))
        self.assertEqual(result['present'], Decimal(80))
        self.assertEqual(result['result'], Decimal(30))
        self.assertEqual(result['pending'], 1)
        self.assertIsNone(positions[1]['result'])
        response = self.client.get('/fin2/contas/1/')
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn('Resultado das aplicações', html)
        self.assertLess(html.index('tab=resultado'), html.index('tab=aplicacoes'))

    def test_institution_details_scope_accounts_and_movements(self):
        import json
        from django.shortcuts import render
        with connect(self.fixture.database) as c:
            batch = c.execute('SELECT batch_id FROM import_batch').fetchone()[0]
            for record, table, identifier, payload in [
                ('a'*64, 'fin1_instituicao', 1, {'nome':'Instituição A'}),
                ('b'*64, 'fin1_instituicao', 2, {'nome':'Instituição B'}),
                ('c'*64, 'fin1_conta', 2, {'nome':'Conta B','instituicao_id':2})]:
                c.execute('INSERT INTO source_record VALUES (?,?,?,?,?,?)',
                          [record,batch,'db.sqlite3',table,identifier,json.dumps(payload)])
            c.execute("UPDATE source_record SET payload=? WHERE table_name='fin1_conta' AND legacy_id=1",
                      [json.dumps({'nome':'Conta A','instituicao_id':1})])
            for account, in c.execute('SELECT source_record_id FROM portfolio.account').fetchall():
                c.execute("""INSERT INTO ledger.manual_event
                    (event_id,account_source_record_id,event_type,settlement_date,currency,amount,description)
                    VALUES (?,?,'deposit','2024-01-01','BRL',100,?)""", [account,account,account])
        for tab in ('resultado','contas','aplicacoes','movimentacoes'):
            with patch('fin2.dashboard.ledger_views.render', wraps=render) as rendered:
                response = self.client.get('/fin2/instituicoes/1/', {'tab':tab})
                self.assertEqual(response.status_code,200)
                data = rendered.call_args.args[2]
                self.assertEqual([a['legacy_id'] for a in data['institution_accounts']],[1])
                self.assertTrue(all(p['account_id']==1 for p in data['applications']))
                self.assertTrue(data['rows'])
                self.assertTrue(all(r['account_id']==1 for r in data['rows']))
        self.assertEqual(self.client.get('/fin2/instituicoes/99999/').status_code,404)
        self.assertIn('/fin2/instituicoes/1/?',self.client.get('/fin2/').content.decode())

    def test_investor_details_scope_accounts_and_movements(self):
        import json
        from django.shortcuts import render
        with connect(self.fixture.database) as c:
            batch = c.execute('SELECT batch_id FROM import_batch').fetchone()[0]
            for record, table, identifier, payload in [
                ('a'*64, 'fin1_titular', 1, {'nome':'Titular A'}),
                ('b'*64, 'fin1_titular', 2, {'nome':'Titular B'}),
                ('c'*64, 'fin1_conta', 2, {'nome':'Conta B','titular_id':2})]:
                c.execute('INSERT INTO source_record VALUES (?,?,?,?,?,?)',
                          [record,batch,'db.sqlite3',table,identifier,json.dumps(payload)])
            c.execute("UPDATE source_record SET payload=? WHERE table_name='fin1_conta' AND legacy_id=1",
                      [json.dumps({'nome':'Conta A','titular_id':1})])
            for account, in c.execute('SELECT source_record_id FROM portfolio.account').fetchall():
                c.execute("""INSERT INTO ledger.manual_event
                    (event_id,account_source_record_id,event_type,settlement_date,currency,amount,description)
                    VALUES (?,?,'deposit','2024-01-01','BRL',100,?)""", [account,account,account])
        for tab in ('resultado','contas','aplicacoes','movimentacoes'):
            with patch('fin2.dashboard.ledger_views.render', wraps=render) as rendered:
                response = self.client.get('/fin2/titulares/1/', {'tab':tab})
                self.assertEqual(response.status_code,200)
                data = rendered.call_args.args[2]
                self.assertEqual([a['legacy_id'] for a in data['investor_accounts']],[1])
                self.assertTrue(all(p['account_id']==1 for p in data['applications']))
                self.assertTrue(data['rows'])
                self.assertTrue(all(r['account_id']==1 for r in data['rows']))
        self.assertEqual(self.client.get('/fin2/titulares/99999/').status_code,404)
        self.assertIn('/fin2/titulares/1/?',self.client.get('/fin2/').content.decode())

    def test_product_detail_excludes_other_products_in_same_account(self):
        import json
        from django.shortcuts import render
        with connect(self.fixture.database) as c:
            batch = c.execute('SELECT batch_id FROM import_batch').fetchone()[0]
            account = c.execute('SELECT source_record_id FROM portfolio.account LIMIT 1').fetchone()[0]
            for record, table, identifier, payload in [
                ('a'*64,'fin1_produto',1,{'nome':'Produto A'}),
                ('b'*64,'fin1_produto',2,{'nome':'Produto B'}),
                ('c'*64,'fin1_ativo',1,{'nome':'Ativo A','produto_id':1}),
                ('d'*64,'fin1_ativo',2,{'nome':'Ativo B','produto_id':2}),
                ('e'*64,'fin1_aplicacao',2,{'nome':'Aplicação B','conta_id':1,'ativo_id':2})]:
                c.execute('INSERT INTO source_record VALUES (?,?,?,?,?,?)',
                          [record,batch,'db.sqlite3',table,identifier,json.dumps(payload)])
            c.execute("UPDATE source_record SET payload=? WHERE table_name='fin1_aplicacao' AND legacy_id=1",
                      [json.dumps({'nome':'Aplicação A','conta_id':1,'ativo_id':1})])
            for application, in c.execute('SELECT source_record_id FROM portfolio.application').fetchall():
                c.execute("""INSERT INTO ledger.manual_event
                    (event_id,account_source_record_id,application_source_record_id,event_type,settlement_date,currency,amount,description)
                    VALUES (?,?,?,'income','2024-01-01','BRL',100,?)""", [application,account,application,application])
        for tab in ('resultado','contas','aplicacoes','movimentacoes'):
            with patch('fin2.dashboard.ledger_views.render', wraps=render) as rendered:
                response = self.client.get('/fin2/produtos/1/', {'tab':tab})
                self.assertEqual(response.status_code,200)
                data = rendered.call_args.args[2]
                self.assertEqual([p['legacy_id'] for p in data['applications']],[1])
                self.assertEqual([a['legacy_id'] for a in data['product_accounts']],[1])
                if tab == 'movimentacoes':
                    self.assertTrue(data['rows'])
                    self.assertTrue(all(r['application_record']==data['applications'][0]['source_record_id'] for r in data['rows']))
        self.assertEqual(self.client.get('/fin2/produtos/99999/').status_code,404)
        self.assertIn('/fin2/produtos/1/?',self.client.get('/fin2/').content.decode())

    def test_class_detail_excludes_other_classes_in_same_account(self):
        import json
        from django.shortcuts import render
        with connect(self.fixture.database) as c:
            batch = c.execute('SELECT batch_id FROM import_batch').fetchone()[0]
            account = c.execute('SELECT source_record_id FROM portfolio.account LIMIT 1').fetchone()[0]
            for record, table, identifier, payload in [
                ('a'*64,'fin1_classe',1,{'nome':'Classe A'}),
                ('b'*64,'fin1_classe',2,{'nome':'Classe B'}),
                ('c'*64,'fin1_ativo',1,{'nome':'Ativo A','classe_id':1}),
                ('d'*64,'fin1_ativo',2,{'nome':'Ativo B','classe_id':2}),
                ('e'*64,'fin1_aplicacao',2,{'nome':'Aplicação B','conta_id':1,'ativo_id':2})]:
                c.execute('INSERT INTO source_record VALUES (?,?,?,?,?,?)',
                          [record,batch,'db.sqlite3',table,identifier,json.dumps(payload)])
            c.execute("UPDATE source_record SET payload=? WHERE table_name='fin1_aplicacao' AND legacy_id=1",
                      [json.dumps({'nome':'Aplicação A','conta_id':1,'ativo_id':1})])
            for application, in c.execute('SELECT source_record_id FROM portfolio.application').fetchall():
                c.execute("""INSERT INTO ledger.manual_event
                    (event_id,account_source_record_id,application_source_record_id,event_type,settlement_date,currency,amount,description)
                    VALUES (?,?,?,'income','2024-01-01','BRL',100,?)""", [application,account,application,application])
        for tab in ('resultado','contas','aplicacoes','movimentacoes'):
            with patch('fin2.dashboard.ledger_views.render', wraps=render) as rendered:
                response = self.client.get('/fin2/classes/1/', {'tab':tab})
                self.assertEqual(response.status_code,200)
                data = rendered.call_args.args[2]
                self.assertEqual([p['legacy_id'] for p in data['applications']],[1])
                self.assertEqual([a['legacy_id'] for a in data['asset_class_accounts']],[1])
                if tab == 'movimentacoes':
                    self.assertTrue(data['rows'])
                    self.assertTrue(all(r['application_record']==data['applications'][0]['source_record_id'] for r in data['rows']))
        self.assertEqual(self.client.get('/fin2/classes/99999/').status_code,404)
        self.assertIn('/fin2/classes/1/?',self.client.get('/fin2/').content.decode())

    def test_detail_header_uses_record_image_and_parent_links(self):
        import json
        from fin2.dashboard.detail_headers import detail_header
        with connect(self.fixture.database) as c:
            batch = c.execute('SELECT batch_id FROM import_batch').fetchone()[0]
            app = c.execute('SELECT source_record_id FROM portfolio.application LIMIT 1').fetchone()[0]
            c.execute("INSERT INTO source_record VALUES (?,?,'db.sqlite3','fin1_instituicao',9,?)",
                      ['f'*64,batch,json.dumps({'nome':'Instituição pai'})])
            c.execute("UPDATE source_record SET payload=? WHERE table_name='fin1_conta' AND legacy_id=1",
                      [json.dumps({'nome':'Conta pai','instituicao_id':9})])
            c.execute("UPDATE source_record SET payload=? WHERE record_id=?",
                      [json.dumps({'nome':'Aplicação imagem','conta_id':1,'imagem':'app.png'}),app])
            with patch('fin2.dashboard.detail_headers.manifest',return_value={'app.png':{'hash':'a'*64}}):
                header = detail_header(c,app,'year=2024')['detail_header']
            self.assertEqual(header['image']['hash'],'a'*64)
            self.assertEqual([p['url'] for p in header['parents']],
                             ['/fin2/contas/1/?year=2024','/fin2/instituicoes/9/?year=2024'])
            with patch('fin2.dashboard.detail_headers.manifest',return_value={}):
                self.assertIsNone(detail_header(c,app,'')['detail_header']['image'])

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
        self.assertEqual(result['sale_details'][0]['tax_group'],'common')

    def test_day_trade_is_split_from_existing_position(self):
        from datetime import date
        events=[
            {'event_date':date(2024,1,2),'operation':'Compra','quantity':10,'amount':100,
             'gross_amount':100,'allocated_cash':True},
            {'event_date':date(2024,2,1),'operation':'Compra','quantity':8,'amount':96,
             'gross_amount':96,'allocated_cash':True},
            {'event_date':date(2024,2,1),'operation':'Venda','quantity':5,'amount':75,
             'gross_amount':75,'allocated_cash':True},
        ]
        result=_average_cost(events,date(2024,12,31),2024)
        self.assertEqual(result['status'],'calculated')
        self.assertEqual(result['quantity'],Decimal('13'))
        self.assertEqual(result['cost_balance'],Decimal('136'))
        self.assertEqual(result['realized_gain'],Decimal('15'))
        self.assertEqual(result['sale_details'],[{
            'date':date(2024,2,1),'proceeds':Decimal('75'),'gain':Decimal('15'),
            'tax_group':'day_trade','quantity':Decimal('5')}])

    def test_split_preserves_total_cost_and_sale_count(self):
        from datetime import date
        events=[
            {'event_date':date(2024,1,2),'operation':'Compra','quantity':10,'amount':100,
             'gross_amount':100,'allocated_cash':True},
            {'event_date':date(2024,2,1),'operation':'Split','quantity':10,'amount':0,
             'gross_amount':0,'allocated_cash':True},
            {'event_date':date(2024,3,1),'operation':'Venda','quantity':5,'amount':75,
             'gross_amount':75,'allocated_cash':True},
        ]
        result=_average_cost(events,date(2024,12,31),2024)
        self.assertEqual(result['status'],'calculated')
        self.assertEqual(result['quantity'],Decimal('15'))
        self.assertEqual(result['cost_balance'],Decimal('75'))
        self.assertEqual(result['average_cost'],Decimal('5'))
        self.assertEqual(result['realized_gain'],Decimal('50'))
        self.assertEqual(result['sale_count'],1)

    def test_split_with_value_remains_unsupported(self):
        from datetime import date
        events=[
            {'event_date':date(2024,1,2),'operation':'Compra','quantity':10,'amount':100,
             'gross_amount':100,'allocated_cash':True},
            {'event_date':date(2024,2,1),'operation':'Split','quantity':10,'amount':1,
             'gross_amount':1,'allocated_cash':True},
        ]
        self.assertEqual(_average_cost(events,date(2024,12,31))['status'],'unsupported_operation')
        events[1].update(quantity=-10,amount=0,gross_amount=0)
        self.assertEqual(_average_cost(events,date(2024,12,31))['status'],'unsupported_operation')

    def test_later_unsupported_event_does_not_discard_completed_sales(self):
        from datetime import date
        events=[
            {'event_date':date(2024,1,2),'operation':'Compra','quantity':10,'amount':100,
             'gross_amount':100,'allocated_cash':True},
            {'event_date':date(2024,2,2),'operation':'Venda','quantity':5,'amount':75,
             'gross_amount':75,'allocated_cash':True},
            {'event_date':date(2024,3,2),'operation':'Port. Saída','quantity':5,'amount':50,
             'gross_amount':50,'allocated_cash':True},
        ]
        result=_average_cost(events,date(2024,12,31),2024)
        self.assertEqual(result['status'],'unsupported_operation')
        self.assertTrue(result['tax_sales_complete'])
        self.assertEqual(result['sale_details'][0]['gain'],Decimal('25'))

    def test_earlier_unsupported_event_still_blocks_later_sales(self):
        from datetime import date
        events=[
            {'event_date':date(2024,1,2),'operation':'Port. Entr.','quantity':10,'amount':100,
             'gross_amount':100,'allocated_cash':True},
            {'event_date':date(2024,2,2),'operation':'Venda','quantity':5,'amount':75,
             'gross_amount':75,'allocated_cash':True},
        ]
        result=_average_cost(events,date(2024,12,31),2024)
        self.assertEqual(result['status'],'unsupported_operation')
        self.assertFalse(result['tax_sales_complete'])
        self.assertEqual(result['sale_details'],[])

    def test_custody_transfer_carries_cost_without_a_sale(self):
        from datetime import date
        source=[
            {'event_date':date(2024,1,2),'operation':'Compra','quantity':10,'amount':100,
             'gross_amount':100,'allocated_cash':True},
            {'event_date':date(2024,2,1),'operation':'tax_transfer_out','quantity':10,'amount':100,
             'gross_amount':120,'allocated_cash':True},
        ]
        destination=[
            {'event_date':date(2024,2,1),'operation':'tax_transfer_in','quantity':10,'amount':100,
             'gross_amount':120,'allocated_cash':True},
            {'event_date':date(2024,3,1),'operation':'Venda','quantity':4,'amount':60,
             'gross_amount':60,'allocated_cash':True},
        ]
        outgoing=_average_cost(source,date(2024,12,31),2024)
        incoming=_average_cost(destination,date(2024,12,31),2024)
        self.assertEqual((outgoing['status'],outgoing['quantity'],outgoing['sale_count']),
                         ('calculated',Decimal('0'),0))
        self.assertEqual(incoming['cost_balance'],Decimal('60'))
        self.assertEqual(incoming['realized_gain'],Decimal('20'))
        self.assertEqual(incoming['sale_count'],1)

    def test_tax_class_uses_catalog_product_instead_of_numeric_id_or_name_guess(self):
        self.assertEqual(_tax_class({'product_name':'Ação'}),'stocks')
        self.assertEqual(_tax_class({'product_name':'ETF'}),'etf')
        self.assertEqual(_tax_class({'product_name':'Fundo Imobiliário'}),'fii')
        self.assertIsNone(_tax_class({'product_name':'Fundo Renda Fixa'}))
        self.assertIsNone(_tax_class({'product_name':'Previdência Privada'}))

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
        shortcuts=[('classe','◕','Classes'),('produto','▤','Produtos'),
                   ('titular','♟','Titulares'),('instituicao','⛫','Instituições'),
                   ('conta','▣','Contas')]
        positions=[]
        for kind,symbol,label in shortcuts:
            fragment=f'href="/fin2/cadastros/{kind}/?'
            self.assertIn(fragment,html)
            heading=f'<summary><span aria-hidden="true">{symbol}</span> {label}</summary>'
            self.assertIn(heading,html)
            positions.append(html.index(heading))
        self.assertEqual(positions,sorted(positions))
        self.assertLess(html.index('<summary>Visão geral</summary>'),positions[0])
        self.assertLess(positions[-1],html.index('<summary>Dados e auditoria</summary>'))
        self.assertIn('<span>TEST</span></a>',html)
        for group in ('Visão geral','Dados e auditoria','Histórico'):
            self.assertIn(f'<summary>{group}</summary>',html)
        for path in ('posicoes','alocacao','historico','relatorios','caixa','lancamentos','importar','conciliacao',
                     'cotacoes','registros','documentos','revisao'):
            self.assertIn(f'/fin2/{path}/',html)
        for path in ('/fin1/','/fin1/aplicacoes/','/fin1/contas/','/fin1/carteiras/','/fin1/ativos/'):
            self.assertIn(f'href="{path}"',html)
        self.assertNotIn('/fin2/historico/fin1/',html)

    def test_quantity_detail_and_invalid_account(self):
        with connect(self.fixture.database) as c:
            application=c.execute("SELECT source_record_id FROM portfolio.application LIMIT 1").fetchone()[0]
        response = self.client.get(f'/fin2/posicoes/{application}/')
        self.assertEqual(response.status_code,200)
        html = response.content.decode()
        self.assertIn('Resultado da aplicação', html)
        self.assertIn('record-heading', html)
        self.assertIn('Valor investido', html)
        self.assertLess(html.index('tab=resultado'),html.index('tab=movimentacoes'))
        movements = self.client.get(f'/fin2/posicoes/{application}/?tab=movimentacoes')
        self.assertEqual(movements.status_code,200)
        self.assertIn('Movimentações da aplicação',movements.content.decode())
        self.assertIn('<th>Origem</th></tr>',movements.content.decode())
        self.assertNotIn('<h2>Resultado da aplicação</h2>',movements.content.decode())
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

    @patch('fin2.dashboard.views.recover_interrupted',return_value=False)
    def test_running_price_job_keeps_previous_result_visible(self, recover):
        with connect(self.fixture.database) as c:
            batch=c.execute('SELECT batch_id FROM import_batch').fetchone()[0]
            c.execute("""INSERT INTO price_update_job
              (job_id,batch_id,status,created_at,finished_at,message)
              VALUES (? ,?,'completed',now()-INTERVAL 1 MINUTE,now()-INTERVAL 1 MINUTE,?)""",
              ['a'*64,batch,'Resultado anterior'])
            c.execute("""INSERT INTO price_update_job(job_id,batch_id,status,created_at,message)
              VALUES (?,?,'running',now(),'Consultando o último fechamento de PETR4')""",
              ['b'*64,batch])
        html=self.client.get('/fin2/').content.decode()
        self.assertIn('Resultado anterior',html)
        self.assertNotIn('Consultando o último fechamento',html)
        status=self.client.get('/fin2/cotacoes/atualizacao/').json()
        self.assertEqual(status['status'],'running')
        self.assertEqual(status['message'],'Resultado anterior')

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
