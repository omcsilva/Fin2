from decimal import Decimal
import sqlite3
import unittest

from tests import test_fin1_import as fixtures
from warehouse.database import connect


class PortfolioTests(unittest.TestCase):
    def test_quantities_cutoff_and_distinct_applications(self):
        fixture=fixtures.ImportTests()
        fixture.setUp()
        try:
            c=sqlite3.connect(fixture.snapshot/'db.sqlite3')
            c.executescript("""
                CREATE TABLE fin1_operacao(id INTEGER PRIMARY KEY,nome TEXT,multQuant INTEGER,multValor INTEGER);
                INSERT INTO fin1_operacao VALUES(1,'Compra',1,1),(2,'Venda',-1,-1);
                ALTER TABLE fin1_aplicacao ADD COLUMN em_carteira REAL;
                UPDATE fin1_aplicacao SET em_carteira=12 WHERE id=1;
                INSERT INTO fin1_aplicacao VALUES(2,1,0);
                ALTER TABLE fin1_movimentacao ADD COLUMN operacao_id INTEGER DEFAULT 1;
                ALTER TABLE fin1_movimentacao ADD COLUMN quant REAL DEFAULT 0;
                INSERT INTO fin1_movimentacao VALUES(2,1,NULL,'2026-01-01','2026-01-01',1,10);
                INSERT INTO fin1_movimentacao VALUES(3,1,NULL,'2026-02-01','2026-02-01',2,-3);
                INSERT INTO fin1_movimentacao VALUES(4,1,NULL,'2027-01-01','2027-01-01',1,5);
            """)
            c.close()
            fixture.manifest()
            fixture.run_import()
            with connect(fixture.database) as db:
                row=db.execute('SELECT all_settled_quantity,quantity_at_cutoff,legacy_delta,unsettled_count,future_count FROM portfolio.quantity_check WHERE application_id=1').fetchone()
                self.assertEqual(row,(Decimal('12'),Decimal('7'),Decimal('0'),1,1))
                self.assertEqual(db.execute('SELECT count(*) FROM portfolio.position').fetchone()[0],2)
                self.assertEqual(db.execute('SELECT count(*) FROM document_record_link').fetchone()[0],2)
        finally:
            fixture.tearDown()


if __name__ == '__main__':
    unittest.main()
