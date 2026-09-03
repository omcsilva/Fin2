CREATE TABLE ledger.file_import (
  import_id VARCHAR PRIMARY KEY, sha256 VARCHAR NOT NULL UNIQUE,
  original_filename VARCHAR NOT NULL, storage_key VARCHAR NOT NULL,
  media_type VARCHAR NOT NULL, status VARCHAR NOT NULL CHECK(status IN ('preview','committed','rejected')),
  row_count INTEGER NOT NULL, error_count INTEGER NOT NULL,
  preview JSON NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  committed_at TIMESTAMPTZ
);
CREATE TABLE ledger.file_import_event (
  import_id VARCHAR NOT NULL, row_number INTEGER NOT NULL,
  event_id VARCHAR NOT NULL UNIQUE, PRIMARY KEY(import_id,row_number)
);
