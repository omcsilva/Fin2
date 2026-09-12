-- Rejecting a load now discards its staging entirely, so the columns that only
-- served to record the rejection decision are no longer used.
ALTER TABLE ledger.file_import DROP COLUMN rejection_reason;
ALTER TABLE ledger.file_import DROP COLUMN rejected_at;

-- Rebuilt here because 0056 had to drop it to allow the two removals above.
CREATE UNIQUE INDEX file_import_document_id ON ledger.file_import(document_id);
