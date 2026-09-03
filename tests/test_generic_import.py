import unittest
from decimal import Decimal
import json

from fin2.imports.generic import stage,commit,reject
from tests import test_fin1_import as fixtures
from warehouse.database import connect

HEADER=b'account,application,type,trade_date,settlement_date,currency,quantity,amount,description\n'


class GenericImportTests(unittest.TestCase):
    def test_preview_dedup_preservation_and_atomic_commit(self):
        f=fixtures.ImportTests();f.setUp()
        try:
            f.run_import()
            with connect(f.database) as db:account=db.execute('select source_record_id from portfolio.account').fetchone()[0]
            body=HEADER+(account+',,deposit,,2026-08-31,BRL,,"1.234,56",Aporte\n').encode()
            identifier,status=stage(f.database,f.database.parent/'documents','events.csv',body,'text/csv')
            self.assertEqual(status,'preview')
            self.assertEqual(stage(f.database,f.database.parent/'documents','events.csv',body)[0],identifier)
            with connect(f.database) as db:
                item=db.execute('select row_count,error_count,status,storage_key,adapter_id,adapter_version,document_type,detection_confidence,document_id from ledger.file_import').fetchone()
                self.assertEqual(item[:3],(1,0,'preview'))
                self.assertTrue((f.database.parent/'documents'/item[3]).is_file())
                self.assertEqual(item[4:8],('generic-ledger','1','transaction_file',90))
                self.assertIsNotNone(item[8])
            self.assertEqual(commit(f.database,identifier),1)
            with connect(f.database) as db:
                self.assertEqual(db.execute('select status from ledger.file_import').fetchone()[0],'committed')
                self.assertEqual(db.execute('select amount from ledger.manual_event').fetchone()[0],Decimal('1234.5600'))
                self.assertEqual(db.execute('select count(*) from ledger.audit_log').fetchone()[0],1)
                self.assertEqual(db.execute("select source_locator->>'line' from ledger.file_import_event").fetchone()[0],'2')
                self.assertEqual(db.execute('select count(*) from ledger.manual_event_document').fetchone()[0],1)
        finally:f.tearDown()

    def test_unknown_content_is_not_accepted_by_extension_alone(self):
        f=fixtures.ImportTests();f.setUp()
        try:
            f.run_import()
            with self.assertRaisesRegex(ValueError,'Nenhum adaptador'):
                stage(f.database,f.database.parent/'documents','unknown.csv',b'not,a,ledger\n1,2,3\n')
        finally:f.tearDown()

    def test_rejection_preserves_file_and_prevents_commit(self):
        f=fixtures.ImportTests();f.setUp()
        try:
            f.run_import()
            with connect(f.database) as db:account=db.execute('select source_record_id from portfolio.account').fetchone()[0]
            body=HEADER+(account+',,deposit,,2026-08-31,BRL,,10,Aporte\n').encode()
            identifier,_=stage(f.database,f.database.parent/'documents','rejected.csv',body)
            reject(f.database,identifier,'Documento incorreto')
            with connect(f.database) as db:
                item=db.execute('select status,rejection_reason,storage_key from ledger.file_import where import_id=?',[identifier]).fetchone()
            self.assertEqual(item[:2],('rejected','Documento incorreto'))
            self.assertTrue((f.database.parent/'documents'/item[2]).is_file())
            with self.assertRaisesRegex(ValueError,'indisponível'):commit(f.database,identifier)
        finally:f.tearDown()

    def test_brokerage_fee_is_allocated_by_gross_trade_value(self):
        f=fixtures.ImportTests();f.setUp()
        try:
            f.run_import()
            with connect(f.database) as db:
                account,application=db.execute("""select a.source_record_id,ap.source_record_id
                  from portfolio.account a join portfolio.application ap on ap.batch_id=a.batch_id and ap.account_id=a.legacy_id limit 1""").fetchone()
                rows=[
                  {'row_number':1,'source_locator':{'page':1,'item':1},'account_record':account,'application_record':application,'event_type':'buy','trade_date':'2026-01-01','settlement_date':'2026-01-01','currency':'BRL','quantity':'1','amount':'-100','description':'Compra 1','errors':[],'allocation_role':'trade','allocation_weight':'100'},
                  {'row_number':2,'source_locator':{'page':1,'item':2},'account_record':account,'application_record':application,'event_type':'buy','trade_date':'2026-01-01','settlement_date':'2026-01-01','currency':'BRL','quantity':'1','amount':'-300','description':'Compra 2','errors':[],'allocation_role':'trade','allocation_weight':'300'},
                  {'row_number':3,'source_locator':{'page':1,'item':3},'account_record':account,'application_record':None,'event_type':'fee','trade_date':'2026-01-01','settlement_date':'2026-01-01','currency':'BRL','quantity':None,'amount':'-4','description':'Emolumentos','errors':[],'allocation_role':'expense'}]
                db.execute("""insert into ledger.file_import
                  (import_id,sha256,original_filename,storage_key,media_type,status,row_count,error_count,preview,byte_size)
                  values ('a','b','note.pdf','x','application/pdf','preview',3,0,?,1)""",[json.dumps(rows)])
            self.assertEqual(commit(f.database,'a'),3)
            with connect(f.database) as db:
                allocations=db.execute('select amount from ledger.file_import_event_allocation order by amount').fetchall()
            self.assertEqual(allocations,[(Decimal('1.0000'),),(Decimal('3.0000'),)])
        finally:f.tearDown()

    def test_statement_metadata_becomes_balance_observation(self):
        f=fixtures.ImportTests();f.setUp()
        try:
            f.run_import()
            with connect(f.database) as db:
                account,batch=db.execute('select source_record_id,batch_id from portfolio.account limit 1').fetchone()
                document=db.execute('select document_id from source_document limit 1').fetchone()[0]
                rows=[{'row_number':1,'source_locator':{'page':2,'line':10},'account_record':account,
                  'application_record':None,'event_type':'deposit','trade_date':'2026-01-02',
                  'settlement_date':'2026-01-02','currency':'USD','quantity':None,'amount':'100',
                  'description':'Journal','errors':[]}]
                metadata={'period_start':'2026-01-01','period_end':'2026-01-31','currency':'USD',
                          'opening_balance':'10','closing_balance':'110','source_page':2}
                db.execute("""insert into ledger.file_import
                  (import_id,sha256,original_filename,storage_key,media_type,status,row_count,error_count,
                   preview,byte_size,batch_id,document_id,document_metadata)
                  values ('statement','statement-hash','statement.pdf','x','application/pdf','preview',1,0,?,1,?,?,?)""",
                  [json.dumps(rows),batch,document,json.dumps(metadata)])
            commit(f.database,'statement')
            with connect(f.database) as db:
                observation=db.execute("""select period_start,period_end,opening_balance,closing_balance,source_page
                  from ledger.statement_balance_observation where document_id=?""",[document]).fetchone()
            self.assertEqual(observation[2:],(Decimal('10.0000'),Decimal('110.0000'),2))
        finally:f.tearDown()

    def test_invalid_row_cannot_commit(self):
        f=fixtures.ImportTests();f.setUp()
        try:
            f.run_import();body=HEADER+b'UNKNOWN,,deposit,,2026-08-31,BRL,,10,Invalid\n'
            identifier,_=stage(f.database,f.database.parent/'documents','bad.csv',body)
            with self.assertRaisesRegex(ValueError,'erros'):commit(f.database,identifier)
            with connect(f.database) as db:self.assertEqual(db.execute('select count(*) from ledger.manual_event').fetchone()[0],0)
        finally:f.tearDown()
