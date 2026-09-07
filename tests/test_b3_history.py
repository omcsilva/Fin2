from datetime import datetime,timezone
from decimal import Decimal
from io import BytesIO
import sqlite3,unittest
from zipfile import ZipFile

from fin2.portfolio.b3_history import capture,parse
from tests import test_fin1_import as fixtures
from warehouse.database import connect


def archive(symbol='PETR4',close='0000000001250',trading_date='20250102'):
    header='00COTAHIST.2025BOVESPA 20260101'+' '*214
    row=list(' '*245)
    row[0:2]='01';row[2:10]=trading_date;row[12:24]=f'{symbol:<12}'
    row[24:27]='010';row[108:121]=close;row=''.join(row)
    trailer='99'+' '*243
    output=BytesIO()
    with ZipFile(output,'w') as z:z.writestr('COTAHIST.2025.TXT','\r\n'.join((header,row,trailer)))
    return output.getvalue()


class B3HistoryTests(unittest.TestCase):
    def test_parse_and_capture_official_unadjusted_close(self):
        body=archive()
        self.assertEqual(parse(body,{'PETR4'}),[('PETR4',datetime(2025,1,2).date(),Decimal('12.5'))])
        f=fixtures.ImportTests();f.setUp()
        try:
            c=sqlite3.connect(f.snapshot/'db.sqlite3');c.executescript("""
              CREATE TABLE fin1_moeda(id INTEGER PRIMARY KEY,abrev TEXT);INSERT INTO fin1_moeda VALUES(1,'REAL');
              CREATE TABLE fin1_ativo(id INTEGER PRIMARY KEY,nome TEXT,abrev TEXT,moeda_id INTEGER);
              INSERT INTO fin1_ativo VALUES(1,'Petrobras','PETR4',1);
            """);c.close();f.manifest();f.run_import()
            with connect(f.database) as db:
                result=capture(db,'COTAHIST_A2025.ZIP',body,datetime(2026,9,6,tzinfo=timezone.utc))
                self.assertEqual(result['points'],1)
                self.assertEqual(db.execute('select close,adjusted_close,provider from market.daily_close_series').fetchone(),
                                 (Decimal('12.5000000000'),None,'b3_cotahist'))
                self.assertEqual(db.execute('select response_body from market.b3_history_capture').fetchone()[0],body)
        finally:f.tearDown()

    def test_rejects_non_cotahist_zip(self):
        with self.assertRaises(ValueError):parse(b'not a zip',{'PETR4'})

    def test_historical_symbol_alias_maps_to_canonical_asset(self):
        body=archive('BVMF3',trading_date='20170707')
        f=fixtures.ImportTests();f.setUp()
        try:
            c=sqlite3.connect(f.snapshot/'db.sqlite3');c.executescript("""
              CREATE TABLE fin1_moeda(id INTEGER PRIMARY KEY,abrev TEXT);INSERT INTO fin1_moeda VALUES(1,'REAL');
              CREATE TABLE fin1_ativo(id INTEGER PRIMARY KEY,nome TEXT,abrev TEXT,moeda_id INTEGER);
              INSERT INTO fin1_ativo VALUES(1,'B3','B3SA3',1);
            """);c.close();f.manifest();f.run_import()
            with connect(f.database) as db:
                result=capture(db,'COTAHIST_A2025.ZIP',body,datetime(2026,9,6,tzinfo=timezone.utc))
                self.assertEqual(result['points'],1)
                self.assertEqual(db.execute('select symbol from market.daily_close_series').fetchone()[0],'B3SA3')
        finally:f.tearDown()


if __name__=='__main__':unittest.main()
