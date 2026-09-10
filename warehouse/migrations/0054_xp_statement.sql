-- Documentary evidence is independent of financial confirmation.
CREATE TABLE ledger.xp_account_binding (
  account_number VARCHAR PRIMARY KEY,
  account_record VARCHAR NOT NULL UNIQUE,
  holder VARCHAR NOT NULL,
  reason VARCHAR NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE ledger.xp_statement (
  import_id VARCHAR PRIMARY KEY,
  account_record VARCHAR NOT NULL,
  documented_at TIMESTAMPTZ,
  financial_status VARCHAR NOT NULL DEFAULT 'pending' CHECK(financial_status IN ('pending','confirmed'))
);
CREATE TABLE ledger.xp_statement_line (
  import_id VARCHAR NOT NULL,
  line_number INTEGER NOT NULL,
  fingerprint VARCHAR NOT NULL,
  raw JSON NOT NULL,
  decision JSON,
  PRIMARY KEY(import_id,line_number)
);
CREATE TABLE ledger.xp_statement_decision (
  decision_id VARCHAR PRIMARY KEY,
  import_id VARCHAR NOT NULL,
  line_number INTEGER NOT NULL,
  payload JSON NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE ledger.xp_statement_link (
  import_id VARCHAR NOT NULL,
  line_number INTEGER NOT NULL,
  entry_id VARCHAR NOT NULL,
  PRIMARY KEY(import_id,line_number,entry_id)
);
CREATE TABLE ledger.xp_statement_claim (
  account_record VARCHAR NOT NULL,
  fingerprint VARCHAR NOT NULL,
  import_id VARCHAR NOT NULL,
  line_number INTEGER NOT NULL,
  PRIMARY KEY(account_record,fingerprint)
);
ALTER TABLE ledger.statement_balance_observation ADD COLUMN source_locator JSON;
ALTER TABLE ledger.statement_balance_observation ADD COLUMN opening_inferred BOOLEAN DEFAULT false;
