# Tests

`test_fin1_import.py` tests repeat import, links, payload preservation, corruption rejection, rollback, and migration checksums with synthetic snapshots. `test_dashboard.py` tests read-only routes, escaped HTML, download behavior, invalid resources, absent databases, CSRF, and document path/integrity protection. Run `.\.venv\Scripts\python.exe -m unittest discover -v`. Keep real Fin1 data outside the checkout.
