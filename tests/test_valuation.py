from decimal import Decimal
import sqlite3
import unittest

from tests import test_fin1_import as fixtures
from warehouse.database import connect


class ValuationTests(unittest.TestCase):
    def test_prices_coverage_and_currency_separation(self):
        fixture=fixtures.ImportTests();fixture.setUp()
        try:
            c=sqlite3.connect(fixture.snapshot/'db.sqlite3')
            c.executescript("""
                CREATE TABLE fin1_moeda(id INTEGER PRIMARY KEY,nome TEXT,abrev TEXT);
                INSERT INTO fin1_moeda VALUES(1,'Real','BRL'),(2,'Dollar','USD');
                CREATE TABLE fin1_ativo(id INTEGER PRIMARY KEY,nome TEXT,moeda_id INTEGER,cotacao REAL,dt_cotacao TEXT);
                INSERT INTO fin1_ativo VALUES(1,'Current',1,10,'2026-08-30'),(2,'Stale',2,5,'2026-01-01'),(3,'Missing',1,NULL,NULL),(4,'Future',1,99,'2027-01-01');
                CREATE TABLE fin1_operacao(id INTEGER PRIMARY KEY,nome TEXT,multQuant INTEGER,multValor INTEGER);
                INSERT INTO fin1_operacao VALUES(1,'Buy',1,1);
                ALTER TABLE fin1_aplicacao ADD COLUMN ativo_id INTEGER;
                ALTER TABLE fin1_aplicacao ADD COLUMN em_carteira REAL;
                UPDATE fin1_aplicacao SET ativo_id=1,em_carteira=2;
                INSERT INTO fin1_aplicacao VALUES(2,1,2,3),(3,1,3,1),(4,1,4,1),(5,1,1,9);
                ALTER TABLE fin1_movimentacao ADD COLUMN operacao_id INTEGER DEFAULT 1;
                ALTER TABLE fin1_movimentacao ADD COLUMN quant REAL DEFAULT 0;
            """)
            for identifier,quantity in [(1,2),(2,3),(3,1),(4,1),(5,1)]:
                c.execute('INSERT INTO fin1_movimentacao VALUES(?,?,NULL,?,?,1,?)',[identifier+1,identifier,'2026-08-01','2026-08-01',quantity])
            c.commit();c.close();fixture.manifest();fixture.run_import()
            with connect(fixture.database) as db:
                states=dict(db.execute('SELECT legacy_id,valuation_status FROM portfolio.valuation').fetchall())
                self.assertEqual(states,{1:'priced',2:'stale_price',3:'missing_price',4:'future_price',5:'quantity_review'})
                totals=dict(db.execute('SELECT currency,reference_subtotal FROM portfolio.valuation_totals').fetchall())
                self.assertEqual(totals,{'BRL':Decimal('20'),'USD':Decimal('15')})
                self.assertEqual(db.execute('SELECT sum(excluded_count) FROM portfolio.valuation_totals').fetchone()[0],3)
                self.assertEqual(db.execute('SELECT percentage FROM portfolio.allocation ORDER BY currency').fetchall(),[(100.0,),(100.0,)])
        finally:fixture.tearDown()
