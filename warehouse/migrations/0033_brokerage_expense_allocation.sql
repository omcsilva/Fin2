-- Trace the proportional allocation of brokerage-note costs to trades.
CREATE TABLE ledger.file_import_event_allocation (
  expense_event_id VARCHAR NOT NULL,
  trade_event_id VARCHAR NOT NULL,
  amount DECIMAL(28,4) NOT NULL CHECK(amount>=0),
  method VARCHAR NOT NULL DEFAULT 'gross_value_pro_rata',
  PRIMARY KEY(expense_event_id,trade_event_id)
);
