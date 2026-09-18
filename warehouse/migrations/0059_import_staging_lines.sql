-- Mutable pre-ledger rows. The raw extraction is kept beside the normalized
-- projection so review edits never rewrite the imported evidence.
CREATE TABLE ledger.import_staging_line (
  import_id VARCHAR NOT NULL,
  row_number INTEGER NOT NULL,
  source_locator JSON NOT NULL,
  raw JSON NOT NULL,
  normalized JSON NOT NULL,
  state VARCHAR NOT NULL DEFAULT 'pending'
    CHECK (state IN ('pending','ready','rejected')),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (import_id, row_number)
);
