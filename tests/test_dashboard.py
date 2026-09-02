import os
from pathlib import Path
import unittest
from unittest.mock import patch

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django
django.setup()
from django.test import Client, override_settings

from tests import test_fin1_import as fixtures
from warehouse.database import connect


class DashboardTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.ImportTests()
        self.fixture.setUp()
        self.fixture.run_import()
        self.settings = override_settings(WAREHOUSE_PATH=self.fixture.database,
            DOCUMENT_ROOT=self.fixture.database.parent / "documents", ALLOWED_HOSTS=["testserver"])
        self.settings.enable()
        self.client = Client(enforce_csrf_checks=True)
        with connect(self.fixture.database) as c:
            self.document = c.execute("SELECT document_id FROM source_document").fetchone()[0]
            self.record = c.execute("SELECT record_id FROM source_record WHERE table_name='fin1_doc'").fetchone()[0]

    def tearDown(self):
        self.settings.disable()
        self.fixture.tearDown()

    def test_pages_and_escaped_legacy_html(self):
        for path in ("/fin2/", "/fin2/posicoes/", "/fin2/caixa/", "/fin2/caixa/?account=1", "/fin2/alocacao/", "/fin2/registros/", "/fin2/documentos/", "/fin2/revisao/", f"/fin2/documentos/{self.document}/"):
            response = self.client.get(path)
            self.assertEqual(response.status_code,200,path)
            self.assertIn("no-store",response["Cache-Control"])
        response = self.client.get(f"/fin2/registros/{self.record}/")
        self.assertContainsEscaped(response.content.decode())

    def assertContainsEscaped(self, html):
        self.assertIn("&lt;p&gt;synthetic&lt;/p&gt;",html)
        self.assertNotIn("<p>synthetic</p>",html)

    def test_unsupported_content_download_only(self):
        response = self.client.get(f"/fin2/documentos/{self.document}/arquivo/")
        self.assertEqual(response.status_code,200)
        self.assertTrue(response["Content-Disposition"].startswith("attachment"))
        self.assertIn("sandbox",response["Content-Security-Policy"])
        self.assertEqual(b"".join(response.streaming_content),b"synthetic fixture, not a renderable PDF")
        response.close()

    def test_invalid_resource_and_filters(self):
        self.assertEqual(self.client.get('/fin2/cotacoes/').status_code,200)
        self.assertEqual(self.client.get('/fin2/cotacoes/', {'provider':"';DROP TABLE source_record;--",'q':'<script>'}).status_code,200)
        self.assertEqual(self.client.get('/fin2/cotacoes/?batch=invalid').status_code,404)
        self.assertEqual(self.client.get("/fin2/documentos/invalid/").status_code,404)
        self.assertEqual(self.client.get("/fin2/?batch=invalid").status_code,404)
        self.assertEqual(self.client.get("/fin2/registros/", {"table":"';DROP TABLE source_record;--"}).status_code,200)
        self.assertEqual(self.client.get("/fin2/registros/?page=99999999999999999").status_code,200)

    def test_quantity_detail_and_invalid_account(self):
        with connect(self.fixture.database) as c:
            application=c.execute("SELECT source_record_id FROM portfolio.application LIMIT 1").fetchone()[0]
        self.assertEqual(self.client.get(f'/fin2/posicoes/{application}/').status_code,200)
        self.assertEqual(self.client.get(f'/fin2/posicoes/{self.record}/').status_code,404)
        self.assertEqual(self.client.get('/fin2/caixa/?account=999').status_code,404)

    def test_missing_database_is_not_created(self):
        absent = self.fixture.root / "absent.duckdb"
        with override_settings(WAREHOUSE_PATH=absent):
            self.assertEqual(self.client.get("/fin2/").status_code,503)
        self.assertFalse(absent.exists())

    def test_no_post_without_csrf(self):
        self.assertEqual(self.client.post("/fin2/").status_code,403)
        self.assertEqual(self.client.post('/fin2/cotacoes/atualizar/').status_code,403)

    @patch('fin2.dashboard.views.create_price_job',return_value=('a'*64,True))
    def test_background_price_job_start_and_status(self, create_job):
        page=self.client.get('/fin2/')
        self.assertIn('Atualizar preços',page.content.decode())
        token=self.client.cookies['csrftoken'].value
        response=self.client.post('/fin2/cotacoes/atualizar/',{'csrfmiddlewaretoken':token})
        self.assertEqual(response.status_code,202)
        self.assertTrue(response.json()['created'])
        create_job.assert_called_once()
        status=self.client.get('/fin2/cotacoes/atualizacao/')
        self.assertEqual(status.status_code,200)
        self.assertEqual(status.json()['status'],'idle')

    def test_storage_path_cannot_escape_and_corruption_not_served(self):
        with connect(self.fixture.database) as c:
            key = c.execute("SELECT storage_key FROM source_document").fetchone()[0]
        (self.fixture.database.parent / "documents" / key).write_bytes(b"corrupt")
        self.assertEqual(self.client.get(f"/fin2/documentos/{self.document}/arquivo/").status_code,404)
        with connect(self.fixture.database) as c:
            c.execute("UPDATE source_document SET storage_key='../db.sqlite3'")
        self.assertEqual(self.client.get(f"/fin2/documentos/{self.document}/arquivo/").status_code,404)


if __name__ == "__main__":
    unittest.main()
