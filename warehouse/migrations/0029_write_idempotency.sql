-- Browser-generated request keys make repeated form submissions idempotent.
ALTER TABLE ledger.manual_event ADD COLUMN request_key VARCHAR;
CREATE UNIQUE INDEX manual_event_request_key ON ledger.manual_event(request_key);
ALTER TABLE ledger.manual_transfer ADD COLUMN request_key VARCHAR;
CREATE UNIQUE INDEX manual_transfer_request_key ON ledger.manual_transfer(request_key);
