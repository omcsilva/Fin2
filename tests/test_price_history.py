from datetime import datetime,timezone
from decimal import Decimal
import json,sqlite3,unittest
from fin2.portfolio.price_history import capture,parse
from tests import test_fin1_import as fixtures
from warehouse.database import connect

NOW=datetime(2026,8,31,20,tzinfo=timezone.utc)
BODY=json.dumps({'results':[{'requestedSymbol':'PETR4','symbol':'PETR4','changed':False,'data':{'usedInterval':'1d','usedRange':'1mo','historicalDataPrice':[{'date':1788134400,'open':10,'high':13,'low':9,'close':12.5,'volume':100,'adjustedClose':12.4}]}}]}).encode()

class PriceHistoryTests(unittest.TestCase):
 def test_daily_close_is_deduplicated_and_audited(self):
  f=fixtures.ImportTests();f.setUp()
  try:
   c=sqlite3.connect(f.snapshot/'db.sqlite3');c.executescript("""CREATE TABLE fin1_moeda(id INTEGER PRIMARY KEY,abrev TEXT);INSERT INTO fin1_moeda VALUES(1,'REAL');CREATE TABLE fin1_webscrap(id INTEGER PRIMARY KEY,plugin TEXT,multiplicador REAL);INSERT INTO fin1_webscrap VALUES(1,'atuBrAPI',1);CREATE TABLE fin1_ativo(id INTEGER PRIMARY KEY,abrev TEXT,moeda_id INTEGER,webscrap_id INTEGER,cotacao REAL);INSERT INTO fin1_ativo VALUES(1,'PETR4',1,1,9);""");c.close();f.manifest();f.run_import()
   with connect(f.database) as db:
    record=db.execute('select source_record_id from market.asset_catalog').fetchone()[0]
    self.assertEqual(capture(db,[(record,'PETR4')],BODY,NOW)['points'],1)
    capture(db,[(record,'PETR4')],BODY,NOW)
    self.assertEqual(db.execute('select count(*),min(close),min(adjusted_close) from market.daily_close').fetchone(),(1,Decimal('12.5000000000'),Decimal('12.4000000000')))
    self.assertEqual(db.execute('select count(*) from market.history_capture').fetchone()[0],1)
   with self.assertRaises(ValueError): parse(b'{}',{'PETR4'})
  finally:f.tearDown()
