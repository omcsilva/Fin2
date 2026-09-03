-- Rejection is explicit and preserves the original source for audit.
ALTER TABLE ledger.file_import ADD COLUMN rejection_reason VARCHAR;
ALTER TABLE ledger.file_import ADD COLUMN rejected_at TIMESTAMPTZ;
