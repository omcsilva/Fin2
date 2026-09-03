-- Atomic transfers are represented by a header and two linked manual events.
CREATE TABLE ledger.manual_transfer (
  transfer_id VARCHAR PRIMARY KEY,
  source_account_record_id VARCHAR NOT NULL,
  destination_account_record_id VARCHAR NOT NULL,
  settlement_date DATE NOT NULL,
  currency VARCHAR NOT NULL,
  amount DECIMAL(28,4) NOT NULL CHECK(amount>0),
  description VARCHAR NOT NULL,
  reverses_transfer_id VARCHAR,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK(source_account_record_id<>destination_account_record_id),
  UNIQUE(reverses_transfer_id)
);

ALTER TABLE ledger.manual_event ADD COLUMN transfer_id VARCHAR;
CREATE INDEX manual_event_transfer ON ledger.manual_event(transfer_id);
