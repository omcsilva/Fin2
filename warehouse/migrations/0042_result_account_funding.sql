-- Explicit funding for new purchases; historical evidence is not reclassified.
CREATE TABLE ledger.purchase_funding (
    event_id VARCHAR PRIMARY KEY,
    source VARCHAR NOT NULL CHECK (source IN ('result_account','investment_balance','dividends','sales','portability'))
);

CREATE VIEW ledger.purchase_contribution AS
SELECT a.batch_id, m.event_id AS entry_id, m.account_source_record_id,
       m.settlement_date, m.currency, -m.amount AS amount,
       (SELECT min(r.settlement_date) FROM ledger.manual_event r
        WHERE r.reverses_event_id=m.event_id) AS reversed_at
FROM ledger.manual_event m
JOIN ledger.purchase_funding f ON f.event_id=m.event_id AND f.source='result_account'
JOIN portfolio.account a ON a.source_record_id=m.account_source_record_id;

CREATE VIEW ledger.result_account_entry AS
SELECT 'result_account' AS account_key, * EXCLUDE(account_key)
FROM ledger.current_account_entry
UNION ALL
SELECT 'result_account',batch_id,entry_id,settlement_date,currency,amount,
       'external_contribution',reversed_at
FROM ledger.purchase_contribution;

-- All money remaining in custody is part of the investment balance.
CREATE VIEW ledger.investment_cash_entry AS
SELECT e.batch_id,a.source_record_id AS account_source_record_id,e.cash_entry_id AS entry_id,
       e.settlement_date,c.abbreviation AS currency,e.signed_amount AS amount
FROM ledger.cash_entry_canonical e
JOIN portfolio.account a ON a.batch_id=e.batch_id AND a.legacy_id=e.account_id
LEFT JOIN portfolio.currency c ON c.batch_id=a.batch_id AND c.legacy_id=a.currency_id
WHERE NOT EXISTS (SELECT 1 FROM ledger.reconciliation_decision d
  WHERE d.batch_id=e.batch_id AND d.subject_type='cash_entry' AND d.subject_id=e.legacy_id
    AND d.resolution='duplicate_source_row')
UNION ALL
SELECT a.batch_id,m.account_source_record_id,m.event_id,m.settlement_date,m.currency,m.amount
FROM ledger.manual_event m JOIN portfolio.account a ON a.source_record_id=m.account_source_record_id
UNION ALL
SELECT batch_id,account_source_record_id,entry_id,settlement_date,currency,amount
FROM ledger.purchase_contribution
UNION ALL
SELECT batch_id,account_source_record_id,entry_id || ':reversal',reversed_at,currency,-amount
FROM ledger.purchase_contribution WHERE reversed_at IS NOT NULL;
