import os
import unittest
from uuid import uuid4
os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings')
import django
django.setup()
from django.test import Client,override_settings
from tests import test_fin1_import as fixtures
from warehouse.database import connect
from fin2.portfolio.catalog import save,records
from fin2.dashboard.report_scope import scoped_connection
from fin2.portfolio.manual_ledger import create


class ReportStatusTests(unittest.TestCase):
    def setUp(self):
        self.f=fixtures.ImportTests();self.f.setUp();self.f.run_import()
        with connect(self.f.database) as db:
            self.batch=db.execute('select batch_id from import_batch').fetchone()[0]
        self.owner=self.add('titular',nome='Titular de teste')
        self.institution=self.add('instituicao',nome='Instituição de teste')
        self.product=self.add('produto',nome='Produto de teste')
        currency=self.add('moeda',nome='Real',abrev='BRL')
        category=self.add('classe',nome='Classe de teste')
        self.account=self.add('conta',nome='Conta filtrável',titular_id=self.owner['legacy_id'],
            instituicao_id=self.institution['legacy_id'],moeda_id=currency['legacy_id'])
        self.asset=self.add('ativo',nome='Ativo filtrável',abrev='TEST4',produto_id=self.product['legacy_id'],
            moeda_id=currency['legacy_id'],classe_id=category['legacy_id'])
        self.application=self.add('aplicacao',nome='Aplicação filtrável',conta_id=self.account['legacy_id'],ativo_id=self.asset['legacy_id'])
    def tearDown(self): self.f.tearDown()
    def test_automatic_contribution_follows_purchase_visibility_in_reports(self):
        from decimal import Decimal
        from unittest.mock import patch
        from django.shortcuts import render
        event = create(self.f.database,account_record=self.account['record_id'],
            application_record=self.application['record_id'],event_type='buy',
            settlement_date='2026-09-01',currency='BRL',amount=-100,quantity=1,
            description='Compra com aporte vinculado')
        with override_settings(WAREHOUSE_PATH=self.f.database,ALLOWED_HOSTS=['testserver']):
            client = Client()
            def totals(include=False):
                with patch('fin2.dashboard.views.render',wraps=render) as rendered:
                    response = client.get('/fin2/relatorios/',{'include_zeroed':'1'} if include else {})
                    self.assertEqual(response.status_code,200)
                    return next((r for r in rendered.call_args.args[2]['totals'] if r['currency']=='BRL'),
                                {'contributions':Decimal(0),'investment':Decimal(0)})
            baseline = totals(True)
            for kind,item in [('ativo',self.asset),('produto',self.product)]:
                with self.subTest(kind=kind):
                    self.status(kind,item,'ZERADO')
                    filtered = totals()
                    self.assertEqual(filtered['contributions'] or 0,(baseline['contributions'] or 0)-Decimal(100))
                    self.assertEqual(filtered['investment'] or 0,(baseline['investment'] or 0)+Decimal(100))
                    self.assertEqual(totals(True)['contributions'],baseline['contributions'])
                    with connect(self.f.database) as db:
                        self.assertEqual(scoped_connection(db).execute(
                            'SELECT count(*) FROM ledger.purchase_contribution WHERE entry_id=?',[event]).fetchone()[0],0)
                    self.status(kind,item,'')
    def add(self,kind,**values):
        identifier=save(self.f.database,batch=self.batch,kind=kind,values=values,request_key=uuid4().hex)
        with connect(self.f.database) as db:
            return next(row for row in records(db,self.batch,kind) if row['record_id']==identifier)
    def status(self,kind,item,value):
        field='decisao' if kind=='conta' else 'status'
        with connect(self.f.database) as db:
            latest=next(r for r in records(db,self.batch,kind) if r['record_id']==item['record_id'])
        save(self.f.database,batch=self.batch,kind=kind,record_id=item['record_id'],revision=latest['revision'],
             values={**latest['payload'],field:value},request_key=uuid4().hex)
    def test_empty_default_and_hierarchical_filter_for_each_status(self):
        for kind,item in [('titular',self.owner),('instituicao',self.institution),('produto',self.product),('ativo',self.asset),('conta',self.account)]:
            with self.subTest(kind=kind):
                if kind!='conta': self.assertEqual(item['payload']['status'],'')
                self.status(kind,item,'ZERADA' if kind=='conta' else 'ZERADO')
                with connect(self.f.database) as db:
                    sql='SELECT count(*) FROM portfolio.position WHERE source_record_id=?'
                    self.assertEqual(scoped_connection(db).execute(sql,[self.application['record_id']]).fetchone()[0],0)
                    self.assertEqual(scoped_connection(db,True).execute(sql,[self.application['record_id']]).fetchone()[0],1)
                self.status(kind,item,'')
        with connect(self.f.database) as db:
            self.assertEqual(scoped_connection(db).execute('SELECT count(*) FROM portfolio.position WHERE source_record_id=?',
                [self.application['record_id']]).fetchone()[0],1)
    def test_checkbox_reports_and_account_cash_follow_scope(self):
        create(self.f.database,account_record=self.account['record_id'],event_type='deposit',settlement_date='2026-09-01',
            currency='BRL',amount=123,description='Aporte ocultável')
        self.status('conta',self.account,'ZERADA')
        self.status('ativo',self.asset,'ZERADO')
        with override_settings(WAREHOUSE_PATH=self.f.database,ALLOWED_HOSTS=['testserver']):
            client=Client()
            for path in ('','posicoes/','caixa/','alocacao/','relatorios/','cotacoes/',
                         'historico/fin1/','historico/fin1/posicoes/','historico/fin1/caixa/',
                         'historico/fin1/alocacao/','historico/fin1/relatorios/','historico/fin1/cotacoes/'):
                response=client.get('/fin2/'+path)
                self.assertEqual(response.status_code,200,path)
                self.assertIn('Incluir zerados?',response.content.decode())
                self.assertNotIn('Conta filtrável',response.content.decode())
                self.assertNotIn('Ativo filtrável',response.content.decode())
            response=client.get('/fin2/caixa/?include_zeroed=1')
            self.assertIn('Aporte ocultável',response.content.decode())
            self.assertIn('name="include_zeroed" value="1" checked',response.content.decode())
            self.assertIn('include_zeroed=1',response.content.decode())
            self.assertEqual(client.get('/fin2/caixa/?account='+str(self.account['legacy_id'])).status_code,404)
