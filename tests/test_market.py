from decimal import Decimal
from contextlib import closing
import sqlite3
import unittest

from tests import test_fin1_import as fixtures
from warehouse.database import connect


class MarketTests(unittest.TestCase):
    def test_provenance_duplicates_and_snapshot_history(self):
        fixture = fixtures.ImportTests()
        fixture.setUp()
        try:
            with closing(sqlite3.connect(fixture.snapshot/'db.sqlite3')) as c:
                c.executescript("""
                    CREATE TABLE fin1_moeda(id INTEGER PRIMARY KEY,nome TEXT,abrev TEXT);
                    INSERT INTO fin1_moeda VALUES(1,'Real','REAL');
                    CREATE TABLE fin1_webscrap(id INTEGER PRIMARY KEY,plugin TEXT,multiplicador REAL);
                    INSERT INTO fin1_webscrap VALUES(1,'atuBrAPI',100);
                    CREATE TABLE fin1_ativo(id INTEGER PRIMARY KEY,nome TEXT,abrev TEXT,codigo TEXT,cnpj TEXT,
                        moeda_id INTEGER,webscrap_id INTEGER,cotacao REAL,dt_cotacao TEXT);
                    INSERT INTO fin1_ativo VALUES
                        (1,'One','SAME','00123','',1,1,1.25,'2026-08-30'),
                        (2,'Two','SAME',NULL,'  ',1,1,0,NULL),
                        (3,'Three','OTHER',NULL,NULL,1,999,5,'2027-01-01'),
                        (4,'Four','FOUR',NULL,NULL,1,NULL,8,'2025-01-01');
                """)
            fixture.manifest(); fixture.run_import(); fixture.run_import()
            with connect(fixture.database) as db:
                self.assertEqual(db.execute('SELECT count(*) FROM market.price_observation').fetchone()[0],4)
                self.assertEqual(db.execute('SELECT quality FROM market.price_observation ORDER BY asset_id').fetchall(),
                    [('available',),('invalid_price',),('future_price',),('stale_price',)])
                self.assertEqual(db.execute("SELECT raw_value FROM market.identifier_candidate WHERE source_field='codigo'").fetchone()[0],'00123')
                self.assertEqual(db.execute('SELECT count(*) FROM market.identifier_candidate WHERE occurrences>1').fetchone()[0],2)
                self.assertEqual(db.execute("SELECT DISTINCT verification_status FROM market.identifier_candidate").fetchall(),[('unverified',)])
                self.assertEqual(db.execute('SELECT price,currency,source,configured_provider FROM market.price_observation WHERE asset_id=1').fetchone(),
                    (Decimal('1.25'),'REAL','fin1_snapshot','atuBrAPI'))
                self.assertIsNone(db.execute('SELECT provider_record_id FROM market.asset_catalog WHERE legacy_id=3').fetchone()[0])
            with closing(sqlite3.connect(fixture.snapshot/'db.sqlite3')) as c:
                c.execute("UPDATE fin1_ativo SET cotacao=2.5,dt_cotacao='2026-08-31' WHERE id=1")
                c.commit()
            fixture.manifest(); fixture.run_import()
            with connect(fixture.database) as db:
                self.assertEqual(db.execute('SELECT price FROM market.price_observation WHERE asset_id=1 ORDER BY price').fetchall(),[(Decimal('1.25'),),(Decimal('2.5'),)])
                self.assertEqual(db.execute('SELECT DISTINCT occurrences FROM market.identifier_candidate WHERE legacy_id=1 AND source_field=\'codigo\'').fetchall(),[(1,)])
                self.assertEqual(db.execute('SELECT count(*) FROM market.price_observation p JOIN source_record r ON p.source_record_id=r.record_id').fetchone()[0],8)
        finally:
            fixture.tearDown()
