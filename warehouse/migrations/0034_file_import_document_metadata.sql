-- Promote staged sources to the central document catalog and retain statement metadata.
ALTER TABLE ledger.file_import ADD COLUMN batch_id VARCHAR;
ALTER TABLE ledger.file_import ADD COLUMN document_id VARCHAR;
ALTER TABLE ledger.file_import ADD COLUMN document_metadata JSON;
CREATE UNIQUE INDEX file_import_document_id ON ledger.file_import(document_id);
