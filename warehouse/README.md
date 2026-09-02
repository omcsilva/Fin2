# Warehouse

DuckDB persistence and analytical SQL belong here. `database.py` provides offline access and migration checksum validation; `0001_legacy_ingestion.sql` implements the initial audit/ingestion schema. The financial ledger is still pending. See [ingestion commands](../docs/legacy-import.md), the [proposed model](../docs/data-model.md), and [concurrency design](../docs/architecture.md).

- `migrations/`: ordered SQL changes, eventually tracked with versions and checksums.
- `repositories/`: parameterized persistence and transaction boundaries.
- `queries/`: reusable analytical queries and views.

The actual database, original documents, reports, and temporary files must live outside the checkout. SQL migrations are the schema source of truth.
