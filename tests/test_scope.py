import sqlite3
import unittest
import os

os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings')
import django
django.setup()
from django.test import Client, override_settings
from tests import test_fin1_import as fixtures
from warehouse.database import connect


class AnalysisScopeTests(unittest.TestCase):
    def test_portfolio_and_year_scope_and_navigation(self):
        f=fixtures.ImportTests();f.setUp()
        try:
            c=sqlite3.connect(f.snapshot/'db.sqlite3')
            c.executescript("""
              CREATE TABLE fin1_carteira(id INTEGER PRIMARY KEY,nome TEXT);
              INSERT INTO fin1_carteira VALUES(1,'Carteira A'),(2,'Carteira B');
              CREATE TABLE fin1_aplicacao_carteira(id INTEGER PRIMARY KEY,aplicacao_id INTEGER,carteira_id INTEGER);
              INSERT INTO fin1_aplicacao_carteira VALUES(1,1,1),(2,2,2);
              INSERT INTO fin1_aplicacao VALUES(2,1);
              CREATE TABLE fin1_operacao(id INTEGER PRIMARY KEY,nome TEXT,multQuant INTEGER,multValor INTEGER);
              INSERT INTO fin1_operacao VALUES(1,'Compra',1,1);
              ALTER TABLE fin1_movimentacao ADD COLUMN operacao_id INTEGER;
              ALTER TABLE fin1_movimentacao ADD COLUMN quant REAL;
              UPDATE fin1_movimentacao SET operacao_id=1,quant=1;
              INSERT INTO fin1_movimentacao VALUES(2,1,NULL,'2020-06-01','2020-06-01',1,10);
              INSERT INTO fin1_movimentacao VALUES(3,2,NULL,'2021-06-01','2021-06-01',1,20);
            """);c.close();f.manifest();f.run_import()
            settings=override_settings(WAREHOUSE_PATH=f.database,DOCUMENT_ROOT=f.database.parent/'documents',ALLOWED_HOSTS=['testserver'])
            settings.enable()
            try:
                client=Client()
                page=client.get('/fin2/posicoes/?portfolio=1&year=2020')
                self.assertEqual(page.status_code,200)
                html=page.content.decode()
                self.assertIn('Carteira A',html)
                self.assertIn('31/12/2020',html)
                self.assertIn('1 resultados',html)
                self.assertIn('portfolio=1&amp;year=2020',html)
                self.assertNotIn('Carteira B · 2020',html)
                self.assertEqual(client.get('/fin2/alocacao/?portfolio=1&year=2020').status_code,200)
                self.assertEqual(client.get('/fin2/caixa/?portfolio=1&year=2020').status_code,200)
                self.assertEqual(client.get('/fin2/?portfolio=99').status_code,404)
                self.assertEqual(client.get('/fin2/?year=1999').status_code,404)
                with connect(f.database) as db:
                    other=db.execute('SELECT source_record_id FROM portfolio.application WHERE legacy_id=2').fetchone()[0]
                self.assertEqual(client.get(f'/fin2/posicoes/{other}/?portfolio=1&year=2020').status_code,404)
            finally:settings.disable()
        finally:f.tearDown()
