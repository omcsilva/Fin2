-- Store optional user context for staged supporting documents.
ALTER TABLE ledger.import_attachment ADD COLUMN description VARCHAR;
ALTER TABLE ledger.import_attachment ADD COLUMN related_lines JSON;
