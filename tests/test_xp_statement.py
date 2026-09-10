from datetime import datetime
from decimal import Decimal
import io
import json
import unittest
from unittest.mock import patch

from openpyxl import Workbook
from fin2.imports.generic import stage, commit, reject
from fin2.imports.xp_statement import extract
from fin2.imports import xp_reconciliation as xp
from fin2.portfolio.manual_ledger import create
from tests import test_fin1_import as fixtures
from warehouse.database import connect


def workbook(movements=None, holder='ANA TESTE', number='123456', shift=0, future=False, tag=''):
    book = Workbook(); sheet = book.active
    sheet.title = 'Extrato'
    sheet.cell(2, 7, 'Extrato da conta' + tag)
    sheet.cell(3, 7, 'De: 01/01/2025 Até: 31/12/2025')
    sheet.cell(4, 2, holder); sheet.cell(4, 7, 'Conta XP: ' + number)
    sheet.cell(5, 2, 'Saldo total projetado'); sheet.cell(5, 7, 999999)
    for col, value in zip((2,3,4,6,7), ('Movimentação','Liquidação','Lançamento','Valor (R$)','Saldo (R$)')):
        sheet.cell(8+shift, col+shift, value)
    movements = movements if movements is not None else [('2025-01-02','2025-01-02','DIVIDENDOS DE CLIENTES TEST3 S/ 100',10,110)]
    for row, values in enumerate(movements, 9+shift):
        for col, value in zip((2,3,4,6,7), values):
            if col in (2,3): value = datetime.fromisoformat(value)
            sheet.cell(row, col+shift, value)
    row = 9+shift+len(movements)
    sheet.cell(row,2,'Lançamentos futuros')
    if future: sheet.cell(row+1,2,datetime(2026,1,1)); sheet.cell(row+1,6,10000)
    output=io.BytesIO(); book.save(output); book.close(); return output.getvalue()


class XPParserTests(unittest.TestCase):
    def test_shifted_headers_settlement_order_futures_and_decimal(self):
        body=workbook([
            ('2025-01-02','2025-01-06','OPERAÇÕES EM BOLSA PR 02/01/2025 NOTA Nº 54321',-20,100),
            ('2025-01-03','2025-01-03','DIVIDENDOS DE CLIENTES TEST3 S/ 100',10,120),
            ('2025-01-03','2025-01-03','DIVIDENDOS DE CLIENTES TEST3 S/ 100',10,110),
        ],shift=2,future=True)
        metadata,rows=extract(body)
        self.assertEqual(len(rows),3)
        self.assertEqual(metadata['opening_balance'],'100')
        self.assertEqual(metadata['closing_balance'],'100')
        self.assertEqual(metadata['balance_breaks'],0)
        self.assertEqual(rows[0].values['note_number'],'54321')
        self.assertNotEqual(rows[1].values['fingerprint'],rows[2].values['fingerprint'])

    def test_broken_balance_formula_unknown_empty_and_invalid(self):
        meta,rows=extract(workbook([
            ('2025-01-03','2025-01-03','DESCRIÇÃO NOVA',1,999),
            ('2025-01-02','2025-01-02','DIVIDENDOS',10,110)]))
        self.assertTrue(meta['errors']); self.assertEqual(rows[0].values['category'],'unknown')
        meta,rows=extract(workbook([('2025-01-02','2025-01-02','DIVIDENDOS','=1+1',110)]))
        self.assertTrue(rows[0].values['errors'])
        with self.assertRaisesRegex(ValueError,'sem movimentos'): extract(workbook([]))
        with self.assertRaisesRegex(ValueError,'inválido'): extract(b'broken')


class XPFlowTests(unittest.TestCase):
    def setUp(self):
        self.fixture=fixtures.ImportTests(); self.fixture.setUp(); self.fixture.run_import()
        self.db=self.fixture.database; self.documents=self.db.parent/'documents'
        with connect(self.db) as db:
            self.account,self.batch=db.execute('select source_record_id,batch_id from portfolio.account').fetchone()
            db.execute("insert into source_record values (?,?, 'db.sqlite3','fin1_moeda',1,?)",['currency',self.batch,json.dumps({'nome':'Real','abrev':'BRL'})])
            for identifier,kind,legacy,payload in (
                ('investor','fin1_titular',1,{'nome':'Ana Teste'}),
                ('investor2','fin1_titular',2,{'nome':'Bruno Teste'}),
                ('asset','fin1_ativo',1,{'nome':'Teste','abrev':'TEST3'}),
                ('other','fin1_conta',2,{'nome':'XP Bruno','moeda_id':1,'titular_id':2}),
                ('digital','fin1_conta',3,{'nome':'Digital Ana','moeda_id':1,'titular_id':1}),
            ):
                db.execute("insert into source_record values (?,?,'db.sqlite3',?,?,?)",[identifier,self.batch,kind,legacy,json.dumps(payload)])
            db.execute("update source_record set payload=json_merge_patch(payload,?) where record_id=?",[json.dumps({'nome':'XP Ana','moeda_id':1,'titular_id':1}),self.account])
            self.application=db.execute('select source_record_id from portfolio.application').fetchone()[0]
            db.execute("update source_record set payload=json_merge_patch(payload,?) where record_id=?",[json.dumps({'nome':'Teste','ativo_id':1}),self.application])

    def tearDown(self): self.fixture.tearDown()

    def stage(self,body=None,account=None,**options):
        return stage(self.db,self.documents,'extrato.xlsx',body or workbook(),options=dict(account_record=account or self.account,confirm_identity=True,identity_reason='Número e titular conferidos',**options))[0]

    def decision(self,**changes):
        return dict(dict(action='new',event_type='income',application_record=self.application,reason='Provento conferido'),**changes)

    def test_evidence_then_income_and_reexport_no_duplicate(self):
        body=workbook(); identifier=self.stage(body)
        self.assertEqual(self.stage(body),identifier)
        xp.document(self.db,identifier); xp.document(self.db,identifier)
        with connect(self.db) as db:
            self.assertEqual(db.execute('select count(*) from ledger.manual_event').fetchone()[0],0)
            self.assertTrue(db.execute('select opening_inferred from ledger.statement_balance_observation').fetchone()[0])
            self.assertEqual(xp.detail(db,identifier)['counts']['pending'],1)
        xp.review(self.db,identifier,1,self.decision())
        self.assertEqual(commit(self.db,identifier),1)
        second=self.stage(workbook(tag=' reexportado'))
        self.assertEqual(commit(self.db,second),0)
        with connect(self.db) as db:
            self.assertEqual(db.execute('select count(*) from ledger.manual_event').fetchone()[0],1)
            self.assertEqual(db.execute('select count(*) from ledger.xp_statement_link').fetchone()[0],2)
            self.assertEqual(db.execute('select count(*) from ledger.purchase_funding').fetchone()[0],0)
        with self.assertRaises(ValueError): commit(self.db,identifier)

    def test_multiple_holders_and_identity_guard(self):
        self.stage()
        second=self.stage(workbook(holder='BRUNO TESTE',number='777888'),account='other')
        self.assertTrue(second)
        with self.assertRaisesRegex(ValueError,'diverge'): self.stage(workbook(tag='errado'),account='other')
        with self.assertRaisesRegex(ValueError,'Titular'): self.stage(workbook(holder='PESSOA ERRADA',number='999'),account='digital')
        with self.assertRaisesRegex(ValueError,'Confirme'):
            stage(self.db,self.documents,'x.xlsx',workbook(holder='ANA TESTE',number='111'),options={'account_record':'digital'})

    def test_pending_rejection_and_atomic_rollback(self):
        identifier=self.stage(workbook([
            ('2025-01-03','2025-01-03','DIVIDENDOS DE CLIENTES TEST3',20,130),
            ('2025-01-02','2025-01-02','DIVIDENDOS DE CLIENTES TEST3',10,110)]))
        xp.review(self.db,identifier,1,self.decision())
        with self.assertRaisesRegex(ValueError,'todas'): commit(self.db,identifier)
        xp.review(self.db,identifier,2,self.decision())
        original=xp._create
        def fail_second(db,item,row,decision):
            if row['row_number']==2: raise ValueError('falha simulada')
            return original(db,item,row,decision)
        with patch.object(xp,'_create',side_effect=fail_second):
            with self.assertRaisesRegex(ValueError,'simulada'): commit(self.db,identifier)
        with connect(self.db) as db:
            self.assertEqual(db.execute('select count(*) from ledger.manual_event').fetchone()[0],0)
            self.assertEqual(db.execute('select count(*) from ledger.xp_statement_claim').fetchone()[0],0)
        reject(self.db,identifier,'arquivo errado')
        with self.assertRaises(ValueError): commit(self.db,identifier)

    def test_brokerage_many_to_one_and_no_invented_trade(self):
        body=workbook([('2025-01-02','2025-01-02','OPERAÇÕES EM BOLSA PR 02/01/2025 NOTA Nº 123',90,190)])
        identifier=self.stage(body)
        with self.assertRaisesRegex(ValueError,'Categoria'): xp.review(self.db,identifier,1,self.decision())
        events=[create(self.db,account_record=self.account,event_type=kind,settlement_date='2025-01-02',currency='BRL',amount=amount,description=description)
                for kind,amount,description in [('deposit',100,'Nota 123'),('fee',-10,'Despesas nota 123')]]
        xp.review(self.db,identifier,1,self.decision(action='link',entry_ids=events))
        self.assertEqual(commit(self.db,identifier),0)
        with connect(self.db) as db: self.assertEqual(db.execute('select count(*) from ledger.xp_statement_link').fetchone()[0],2)

    def test_duplicate_previews_revalidate_new_existing_event(self):
        first=self.stage(); second=self.stage(workbook(tag='outra consulta'))
        for identifier in (first,second): xp.review(self.db,identifier,1,self.decision())
        self.assertEqual(commit(self.db,first),1); self.assertEqual(commit(self.db,second),0)
        third=self.stage(workbook([('2025-01-04','2025-01-04','DIVIDENDOS DE CLIENTES TEST3',10,110)]))
        xp.review(self.db,third,1,self.decision())
        create(self.db,account_record=self.account,event_type='income',settlement_date='2025-01-04',currency='BRL',amount=10,description='Lançado depois da prévia')
        with self.assertRaisesRegex(ValueError,'mesma data'): commit(self.db,third)

    def test_own_transfer_and_wrong_holder(self):
        identifier=self.stage(workbook([('2025-01-02','2025-01-02','Transferência enviada para a conta digital',-10,90)]))
        with self.assertRaisesRegex(ValueError,'mesmo titular'):
            xp.review(self.db,identifier,1,self.decision(event_type='transfer',counterparty='other'))
        xp.review(self.db,identifier,1,self.decision(event_type='transfer',counterparty='digital'))
        self.assertEqual(commit(self.db,identifier),2)
        with connect(self.db) as db:
            self.assertEqual(db.execute('select sum(amount) from ledger.manual_event').fetchone()[0],0)
            self.assertEqual(db.execute("select count(*) from ledger.current_account_entry where entry_id in (select event_id from ledger.manual_event)").fetchone()[0],0)

    def test_repeated_identical_descriptions_are_distinct(self):
        identifier=self.stage(workbook([
            ('2025-01-02','2025-01-02','DIVIDENDOS DE CLIENTES TEST3',10,120),
            ('2025-01-02','2025-01-02','DIVIDENDOS DE CLIENTES TEST3',10,110)]))
        for line in (1,2): xp.review(self.db,identifier,line,self.decision())
        self.assertEqual(commit(self.db,identifier),2)
        with connect(self.db) as db: self.assertEqual(db.execute('select count(*) from ledger.xp_statement_claim').fetchone()[0],2)

    def test_redemption_tax_requires_pair_and_preserves_two_amounts(self):
        identifier=self.stage(workbook([
            ('2025-01-02','2025-01-02','IRRF S/RESGATE FUNDOS Teste',-5,195),
            ('2025-01-02','2025-01-02','RESGATE Teste',100,200)]))
        with self.assertRaisesRegex(ValueError,'Vincule o imposto'):
            xp.review(self.db,identifier,1,self.decision(event_type='tax'))
        with self.assertRaisesRegex(ValueError,'quantidade'):
            xp.review(self.db,identifier,2,self.decision(event_type='redemption'))
        with connect(self.db) as db:
            document=db.execute('select document_id from source_document where original_filename=?',['note.pdf']).fetchone()[0]
        xp.review(self.db,identifier,1,self.decision(event_type='tax',related_line='2'))
        xp.review(self.db,identifier,2,self.decision(event_type='redemption',quantity='2',document_id=document))
        self.assertEqual(commit(self.db,identifier),2)
        with connect(self.db) as db:
            self.assertEqual(db.execute('select sum(amount) from ledger.manual_event').fetchone()[0],Decimal('95'))
            self.assertEqual(db.execute("select quantity from ledger.manual_event where event_type='redemption'").fetchone()[0],Decimal('2'))

    def test_one_existing_event_cannot_cover_two_rows(self):
        identifier=self.stage(workbook([
            ('2025-01-02','2025-01-02','DIVIDENDOS DE CLIENTES TEST3',10,120),
            ('2025-01-02','2025-01-02','DIVIDENDOS DE CLIENTES TEST3',10,110)]))
        event=create(self.db,account_record=self.account,event_type='income',settlement_date='2025-01-02',currency='BRL',amount=10,description='Provento')
        for line in (1,2): xp.review(self.db,identifier,line,self.decision(action='link',entry_ids=[event]))
        with self.assertRaisesRegex(ValueError,'duas linhas'): commit(self.db,identifier)

    def test_short_holder_names_are_explicitly_associated(self):
        with connect(self.db) as db:
            db.execute("update source_record set payload=? where record_id='investor'",[json.dumps({'nome':'Ana'})])
        identifier=self.stage()
        self.assertTrue(identifier)
        with connect(self.db) as db:
            self.assertEqual(db.execute('select holder from ledger.xp_account_binding').fetchone()[0],'ANA TESTE')

    def test_bulk_review_saves_new_and_existing_without_financial_writes(self):
        identifier=self.stage(workbook([
            ('2025-01-05','2025-01-05','Transferência enviada para a conta digital',-5,130),
            ('2025-01-04','2025-01-04','DIVIDENDOS DE CLIENTES TEST3',20,135),
            ('2025-01-03','2025-01-03','DIVIDENDOS DE CLIENTES TEST3',5,115),
            ('2025-01-02','2025-01-02','DIVIDENDOS DE CLIENTES TEST3',10,110)]))
        create(self.db,account_record=self.account,event_type='income',settlement_date='2025-01-03',currency='BRL',amount=5,description='DIVIDENDOS  DE CLIENTES TEST3')
        with connect(self.db) as db: item=xp.detail(db,identifier)
        self.assertEqual((item['bulk_new_count'],item['bulk_link_count']),(2,1))
        self.assertEqual(xp.bulk_review(self.db,identifier,[p['row_number'] for p in item['bulk_suggestions']],item['bulk_token']),3)
        with connect(self.db) as db:
            item=xp.detail(db,identifier)
            self.assertEqual(item['counts'],{'new':2,'linked':1,'pending':1,'divergent':0})
            self.assertEqual(db.execute('select count(*) from ledger.manual_event').fetchone()[0],1)
            self.assertEqual(db.execute('select count(*) from ledger.xp_statement_decision').fetchone()[0],3)
        with self.assertRaisesRegex(ValueError,'todas'): commit(self.db,identifier)

    def test_bulk_review_rejects_stale_or_forged_selection(self):
        identifier=self.stage()
        with connect(self.db) as db: item=xp.detail(db,identifier)
        with self.assertRaisesRegex(ValueError,'Selecione'): xp.bulk_review(self.db,identifier,[],item['bulk_token'])
        with self.assertRaisesRegex(ValueError,'sem sugestão'): xp.bulk_review(self.db,identifier,[1,999],item['bulk_token'])
        create(self.db,account_record=self.account,event_type='income',settlement_date='2025-01-02',currency='BRL',amount=10,description='Recebido depois de abrir a prévia')
        with self.assertRaisesRegex(ValueError,'mudaram'): xp.bulk_review(self.db,identifier,[1],item['bulk_token'])
        with connect(self.db) as db:
            self.assertEqual(db.execute('select count(*) from ledger.xp_statement_decision').fetchone()[0],0)

    def test_bulk_review_preserves_individual_decisions_and_ambiguous_matches(self):
        identifier=self.stage(workbook([
            ('2025-01-03','2025-01-03','DIVIDENDOS DE CLIENTES TEST3',20,140),
            ('2025-01-02','2025-01-02','DIVIDENDOS DE CLIENTES TEST3',10,120),
            ('2025-01-02','2025-01-02','DIVIDENDOS DE CLIENTES TEST3',10,110)]))
        xp.review(self.db,identifier,1,self.decision(action='pending',reason='Revisar depois'))
        create(self.db,account_record=self.account,event_type='income',settlement_date='2025-01-02',currency='BRL',amount=10,description='DIVIDENDOS DE CLIENTES TEST3')
        with connect(self.db) as db:
            item=xp.detail(db,identifier)
            self.assertEqual(item['bulk_suggestions'],[])
            self.assertEqual(item['rows'][0]['decision']['reason'],'Revisar depois')

    def test_bulk_review_rolls_back_all_decisions_on_error(self):
        identifier=self.stage(workbook([
            ('2025-01-03','2025-01-03','DIVIDENDOS DE CLIENTES TEST3',20,130),
            ('2025-01-02','2025-01-02','DIVIDENDOS DE CLIENTES TEST3',10,110)]))
        with connect(self.db) as db: item=xp.detail(db,identifier)
        original=xp._validate
        def fail_second(db,item,row,decision,used):
            if decision.get('bulk_review_id') and row['row_number']==2: raise ValueError('falha simulada no lote')
            return original(db,item,row,decision,used)
        with patch.object(xp,'_validate',side_effect=fail_second):
            with self.assertRaisesRegex(ValueError,'simulada'):
                xp.bulk_review(self.db,identifier,[1,2],item['bulk_token'])
        with connect(self.db) as db:
            self.assertEqual(db.execute('select count(*) from ledger.xp_statement_decision').fetchone()[0],0)
            self.assertEqual(db.execute('select count(*) from ledger.xp_statement_line where decision is not null').fetchone()[0],0)
