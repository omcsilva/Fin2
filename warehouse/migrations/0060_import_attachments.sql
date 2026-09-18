-- Documents staged as supporting evidence for a parent import.
CREATE TABLE ledger.import_attachment (
  parent_import_id VARCHAR NOT NULL,
  attachment_import_id VARCHAR NOT NULL UNIQUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (parent_import_id, attachment_import_id)
);
