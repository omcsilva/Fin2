-- Identify the parser and retain a format-independent source locator per event.
ALTER TABLE ledger.file_import ADD COLUMN adapter_id VARCHAR DEFAULT 'generic-ledger';
ALTER TABLE ledger.file_import ADD COLUMN adapter_version VARCHAR DEFAULT '1';
ALTER TABLE ledger.file_import ADD COLUMN document_type VARCHAR DEFAULT 'transaction_file';
ALTER TABLE ledger.file_import ADD COLUMN detection_confidence INTEGER;
ALTER TABLE ledger.file_import_event ADD COLUMN source_locator JSON;
