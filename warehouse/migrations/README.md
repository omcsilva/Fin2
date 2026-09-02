# SQL migrations

`0001_legacy_ingestion.sql` creates the audit/ingestion layer. `warehouse.database.migrate` tracks versions/checksums and applies changes transactionally. Run only under exclusive maintenance ownership of the database. Do not modify an applied SQL migration; add a new version.
