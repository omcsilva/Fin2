from datetime import date
from decimal import Decimal
from pathlib import Path
import unittest

from fin2.portfolio.manual_ledger import create,create_transfer,reverse_transfer,reverse,correct
from tests import test_fin1_import as fixtures
from warehouse.database import connect


class ManualLedgerTests(unittest.TestCase):
    def test_validated_atomic_event_and_audit(self):
        f=fixtures.ImportTests();f.setUp()
        try:
            f.run_import()
            with connect(f.database) as c:
                account=c.execute('select source_record_id from portfolio.account').fetchone()[0]
                document=c.execute('select document_id from source_document').fetchone()[0]
            event=create(f.database,account_record=account,event_type='deposit',
                         settlement_date=date(2026,8,31),currency='brl',amount='12.34567',
                         description='  aporte   manual ',document_id=document,request_key='d'*32)
            repeated=create(f.database,account_record=account,event_type='deposit',
                         settlement_date=date(2026,8,31),currency='brl',amount='12.34567',
                         description='  aporte   manual ',document_id=document,request_key='d'*32)
            self.assertEqual(repeated,event)
            with connect(f.database) as c:
                self.assertEqual(c.execute('select amount,currency,description from ledger.manual_event where event_id=?',[event]).fetchone(),(Decimal('12.3457'),'BRL','aporte manual'))
                self.assertEqual(c.execute('select action from ledger.audit_log where entity_id=?',[event]).fetchone()[0],'create')
                self.assertEqual(c.execute('select document_id from ledger.manual_event_document where event_id=?',[event]).fetchone()[0],document)
            replacement=correct(f.database,event,settlement_date='2026-09-01',amount='15',
              description='Aporte corrigido',request_key='f'*32)
            self.assertEqual(correct(f.database,event,settlement_date='2026-09-01',amount='15',
              description='Aporte corrigido',request_key='f'*32),replacement)
            with connect(f.database) as c:
                correction=c.execute("""select r.event_id,n.amount,n.description
                  from ledger.manual_event r join ledger.manual_event n on r.reverses_event_id=?
                  where n.event_id=?""",[event,replacement]).fetchone()
                self.assertEqual((correction[1],correction[2]),(Decimal('15.0000'),'Aporte corrigido'))
                self.assertEqual(c.execute('select count(*) from ledger.manual_event_document where event_id in (?,?)',[correction[0],replacement]).fetchone()[0],2)
            with self.assertRaisesRegex(ValueError,'Conta desconhecida'):
                create(f.database,account_record='missing',event_type='deposit',settlement_date='2026-08-31',currency='BRL',amount=1,description='x')
            with self.assertRaisesRegex(ValueError,'positivo'):
                create(f.database,account_record=account,event_type='deposit',settlement_date='2026-08-31',currency='BRL',amount=-1,description='x')
            with self.assertRaisesRegex(ValueError,'aplicação e quantidade'):
                create(f.database,account_record=account,event_type='buy',settlement_date='2026-08-31',currency='BRL',amount=-1,description='x')
            with self.assertRaisesRegex(ValueError,'resgate exigem'):
                create(f.database,account_record=account,event_type='redemption',settlement_date='2026-08-31',currency='BRL',amount=1,description='x')
            body=b'%PDF-1.4\n%%EOF\n'
            uploaded=create(f.database,account_record=account,event_type='deposit',
              settlement_date='2026-08-31',currency='BRL',amount=1,description='Comprovado',
              upload_filename='comprovante.pdf',upload_body=body,storage_root=f.database.parent/'documents',
              request_key='a'*32)
            with connect(f.database) as c:
                saved=c.execute("""select d.original_filename,d.storage_key,d.byte_size
                  from source_document d join ledger.manual_event_document md using(document_id)
                  where md.event_id=?""",[uploaded]).fetchone()
            self.assertEqual((saved[0],saved[2]),('comprovante.pdf',len(body)))
            self.assertEqual((f.database.parent/'documents'/saved[1]).read_bytes(),body)
            with self.assertRaisesRegex(ValueError,'incompatível'):
                create(f.database,account_record=account,event_type='deposit',settlement_date='2026-08-31',
                  currency='BRL',amount=1,description='Inválido',upload_filename='falso.pdf',
                  upload_body=b'not a pdf',storage_root=f.database.parent/'documents')
            with self.assertRaisesRegex(ValueError,'existente ou um novo'):
                create(f.database,account_record=account,event_type='deposit',settlement_date='2026-08-31',
                  currency='BRL',amount=1,description='Duplicado',document_id=document,
                  upload_filename='comprovante.pdf',upload_body=body,storage_root=f.database.parent/'documents')
        finally: f.tearDown()

    def test_transfer_creates_and_reverses_both_sides_atomically(self):
        f=fixtures.ImportTests();f.setUp()
        try:
            f.run_import()
            destination='b'*64
            with connect(f.database) as c:
                source=c.execute('select source_record_id from portfolio.account').fetchone()[0]
                batch=c.execute('select batch_id from import_batch').fetchone()[0]
                c.execute("""insert into source_record values (? ,?,'db.sqlite3','fin1_moeda',1,
                  '{"id":1,"nome":"Real","abrev":"REAL"}')""",['c'*64,batch])
                c.execute("update source_record set payload=json_merge_patch(payload,'{\"moeda_id\":1}') where record_id=?",[source])
                c.execute("""insert into source_record
                  select ?,batch_id,database_name,table_name,2,
                    json_merge_patch(payload,'{"id":2,"nome":"Destino","moeda_id":1}')
                  from source_record where record_id=?""",[destination,source])
            body=b'%PDF-1.4\n%%EOF\n'
            transfer=create_transfer(f.database,source_account=source,destination_account=destination,
              settlement_date='2026-08-31',amount='100.005',description='Movimentação interna',
              upload_filename='transferencia.pdf',upload_body=body,storage_root=f.database.parent/'documents',
              request_key='e'*32)
            self.assertEqual(create_transfer(f.database,source_account=source,destination_account=destination,
              settlement_date='2026-08-31',amount='100.005',description='Movimentação interna',
              upload_filename='transferencia.pdf',upload_body=body,storage_root=f.database.parent/'documents',
              request_key='e'*32),transfer)
            with connect(f.database) as c:
                rows=c.execute("select event_type,amount,document_id from ledger.manual_event e join ledger.manual_event_document d using(event_id) where transfer_id=? order by amount",[transfer]).fetchall()
                self.assertEqual(len(rows),2)
                self.assertEqual([(r[0],r[1]) for r in rows],[('withdrawal',Decimal('-100.0050')),('deposit',Decimal('100.0050'))])
                self.assertEqual(rows[0][2],rows[1][2])
                event=c.execute('select event_id from ledger.manual_event where transfer_id=? limit 1',[transfer]).fetchone()[0]
            with self.assertRaisesRegex(ValueError,'estorno da transferência'):reverse(f.database,event)
            reversal=reverse_transfer(f.database,transfer)
            with connect(f.database) as c:
                self.assertEqual(c.execute('select sum(amount),count(*) from ledger.manual_event where transfer_id in (?,?)',[transfer,reversal]).fetchone(),(Decimal('0.0000'),4))
                self.assertEqual(c.execute('select action from ledger.audit_log where entity_id=?',[reversal]).fetchone()[0],'reverse')
            with self.assertRaisesRegex(ValueError,'já revertida'):reverse_transfer(f.database,transfer)
        finally:f.tearDown()


if __name__=='__main__': unittest.main()
