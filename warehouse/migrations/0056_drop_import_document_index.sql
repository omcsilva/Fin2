-- Drop the unique index on document_id so the unused rejection columns, which
-- sit before it, can be removed in the next migration.
--
-- DuckDB refuses to drop a column while an index references a later column, and
-- it does not re-plan that constraint mid-transaction, so the index has to be
-- dropped in its own migration. 0057 removes the columns and rebuilds the index
-- with the same name and definition.
DROP INDEX ledger.file_import_document_id;
