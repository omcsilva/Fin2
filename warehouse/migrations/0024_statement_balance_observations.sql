-- Audited balances transcribed from preserved account statements.
-- Observations are evidence at a historical cutoff; they never replace a current balance.
CREATE TABLE ledger.statement_balance_observation (
  observation_id VARCHAR PRIMARY KEY,
  batch_id VARCHAR NOT NULL,
  account_record_id VARCHAR NOT NULL,
  document_id VARCHAR NOT NULL,
  period_start DATE NOT NULL,
  period_end DATE NOT NULL,
  currency VARCHAR NOT NULL,
  opening_balance DECIMAL(28,4) NOT NULL,
  closing_balance DECIMAL(28,4) NOT NULL,
  source_page INTEGER,
  note VARCHAR,
  recorded_at TIMESTAMPTZ NOT NULL DEFAULT current_timestamp,
  UNIQUE (batch_id, account_record_id, document_id)
);

CREATE VIEW ledger.statement_balance_reconciliation AS
SELECT o.*,
  coalesce((SELECT sum(e.signed_amount)
    FROM ledger.cash_entry_canonical e
    JOIN portfolio.account a ON a.batch_id=e.batch_id AND a.legacy_id=e.account_id
    WHERE e.batch_id=o.batch_id AND a.source_record_id=o.account_record_id
      AND e.settlement_date<=o.period_end),0)::DECIMAL(28,4) ledger_closing_balance,
  (o.closing_balance-coalesce((SELECT sum(e.signed_amount)
    FROM ledger.cash_entry_canonical e
    JOIN portfolio.account a ON a.batch_id=e.batch_id AND a.legacy_id=e.account_id
    WHERE e.batch_id=o.batch_id AND a.source_record_id=o.account_record_id
      AND e.settlement_date<=o.period_end),0))::DECIMAL(28,4) closing_difference
FROM ledger.statement_balance_observation o;
