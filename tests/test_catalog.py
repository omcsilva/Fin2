import os,json,unittest
os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings')
import django
django.setup()
from django.test import Client,override_settings
from tests import test_fin1_import as fixtures
from warehouse.database import connect
from fin2.portfolio.catalog import records,save,KINDS

class CatalogTests(unittest.TestCase):
 def setUp(self):
  self.f=fixtures.ImportTests();self.f.setUp();self.f.run_import()
  with connect(self.f.database) as db:self.batch=db.execute('select batch_id from import_batch').fetchone()[0]
 def tearDown(self):self.f.tearDown()
 def test_overlay_preserves_source_and_rejects_stale_update(self):
  with connect(self.f.database) as db:
   original=records(db,self.batch,'conta')[0]
   source=db.execute('select payload from source_record where record_id=?',[original['record_id']]).fetchone()[0]
  # Reference fixtures need not have a complete catalog, so create independent reference data.
  identifier=save(self.f.database,batch=self.batch,kind='carteira',values={'nome':'Nova carteira'},request_key='a'*32)
  save(self.f.database,batch=self.batch,kind='carteira',values={'nome':'Carteira editada'},record_id=identifier,revision=1,request_key='b'*32)
  with self.assertRaisesRegex(ValueError,'outra página'):
   save(self.f.database,batch=self.batch,kind='carteira',values={'nome':'Inválida'},record_id=identifier,revision=1,request_key='c'*32)
  with connect(self.f.database) as db:
   self.assertEqual(db.execute('select name from portfolio.collection where source_record_id=?',[identifier]).fetchone()[0],'Carteira editada')
   self.assertEqual(db.execute('select count(*) from catalog.audit where record_id=?',[identifier]).fetchone()[0],2)
   self.assertEqual(db.execute('select payload from source_record where record_id=?',[original['record_id']]).fetchone()[0],source)
 def test_imported_reference_edit_preserves_raw_payload(self):
  with connect(self.f.database) as db:
   db.execute("insert into source_record values (?,?, 'db.sqlite3','fin1_titular',999,?)",['9'*64,self.batch,json.dumps({'id':999,'nome':'Titular original'})])
   original=records(db,self.batch,'titular')[0]
   source=db.execute('select payload from source_record where record_id=?',[original['record_id']]).fetchone()[0]
  save(self.f.database,batch=self.batch,kind='titular',values={'nome':'Nome atualizado'},record_id=original['record_id'],request_key='d'*32)
  with connect(self.f.database) as db:
   self.assertEqual(db.execute('select payload from source_record where record_id=?',[original['record_id']]).fetchone()[0],source)
   self.assertEqual(db.execute('select name from portfolio.investor where source_record_id=?',[original['record_id']]).fetchone()[0],'Nome atualizado')
 def test_pages_and_create_with_csrf(self):
  with override_settings(WAREHOUSE_PATH=self.f.database,ALLOWED_HOSTS=['testserver'],WRITE_ENABLED=True):
   client=Client(enforce_csrf_checks=True)
   for kind in KINDS:self.assertEqual(client.get('/fin2/cadastros/'+kind+'/').status_code,200,kind)
   self.assertEqual(client.post('/fin2/cadastros/carteira/',{'nome':'Teste'}).status_code,403)
   token=client.cookies['csrftoken'].value
   response=client.post('/fin2/cadastros/carteira/',{'nome':'Teste','request_key':'e'*32,'revision':'0','csrfmiddlewaretoken':token})
   self.assertEqual(response.status_code,302)
   self.assertEqual(client.get(response.url).status_code,200)
 def test_new_account_asset_and_application_can_receive_events(self):
  from fin2.portfolio.manual_ledger import create
  def add(kind,values):
   from uuid import uuid4
   record=save(self.f.database,batch=self.batch,kind=kind,values=values,request_key=uuid4().hex)
   with connect(self.f.database) as db:
    row=next(r for r in records(db,self.batch,kind) if r['record_id']==record)
   return row
  owner=add('titular',{'nome':'Titular novo'})
  institution=add('instituicao',{'nome':'Instituição nova','abrev':'TEST'})
  currency=add('moeda',{'nome':'Real novo','abrev':'BRL'})
  category=add('classe',{'nome':'Classe nova'})
  account=add('conta',{'nome':'Conta nova','titular_id':owner['legacy_id'],'instituicao_id':institution['legacy_id'],'moeda_id':currency['legacy_id']})
  asset=add('ativo',{'nome':'Ativo novo','abrev':'TEST4','moeda_id':currency['legacy_id'],'classe_id':category['legacy_id']})
  application=add('aplicacao',{'nome':'Aplicação nova','conta_id':account['legacy_id'],'ativo_id':asset['legacy_id']})
  portfolio=add('carteira',{'nome':'Carteira nova'})
  add('aplicacao_carteira',{'aplicacao_id':application['legacy_id'],'carteira_id':portfolio['legacy_id']})
  event=create(self.f.database,account_record=account['record_id'],application_record=application['record_id'],
    event_type='buy',settlement_date='2026-09-03',currency='BRL',quantity='2',amount='-20',description='Compra em cadastro novo')
  with connect(self.f.database) as db:
   self.assertEqual(db.execute('select event_type from ledger.manual_event where event_id=?',[event]).fetchone()[0],'buy')
   self.assertEqual(db.execute('select count(*) from source_record where record_id=?',[account['record_id']]).fetchone()[0],0)

 def test_invalid_reference_and_duplicate_are_rejected(self):
  with self.assertRaisesRegex(ValueError,'referência inválida'):
   save(self.f.database,batch=self.batch,kind='conta',values={'nome':'Conta nova','titular_id':999999},request_key='f'*32)
  values={'nome':'Duplicada'}
  first=save(self.f.database,batch=self.batch,kind='carteira',values=values,request_key='1'*32)
  self.assertEqual(save(self.f.database,batch=self.batch,kind='carteira',values=values,request_key='1'*32),first)
  with self.assertRaisesRegex(ValueError,'Já existe'):
   save(self.f.database,batch=self.batch,kind='carteira',values=values,request_key='2'*32)

if __name__=='__main__':unittest.main()
