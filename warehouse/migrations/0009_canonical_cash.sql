ALTER TABLE ledger.reconciliation_decision ADD COLUMN amount_override DECIMAL(28,4);

-- In the imported statements source_value already carries the effective sign.
-- The legacy credit flag is retained as evidence but is not applied a second time.
CREATE VIEW ledger.cash_entry_canonical AS
SELECT d.batch_id,d.source_record_id AS cash_entry_id,d.legacy_id,d.account_id,
       d.settlement_date,d.description,d.source_value AS signed_amount,d.is_credit,
       d.legacy_running_balance,
       sum(d.source_value) OVER (
         PARTITION BY d.batch_id,d.account_id
         ORDER BY d.settlement_timestamp NULLS FIRST,d.legacy_id
         ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
       ) AS reconstructed_running_balance
FROM portfolio.cash_detail d;

CREATE VIEW ledger.cash_account_reconciliation AS
WITH totals AS (
  SELECT batch_id,account_id,count(*) AS entry_count,
         count(*) FILTER (WHERE signed_amount IS NULL) AS incomplete_count,
         sum(signed_amount) AS reconstructed_balance,
         count(*) FILTER (WHERE reconstructed_running_balance<>legacy_running_balance) AS running_mismatch_count
  FROM ledger.cash_entry_canonical
  WHERE account_id IS NOT NULL
  GROUP BY batch_id,account_id
)
SELECT a.batch_id,a.legacy_id AS account_id,a.source_record_id,a.name,a.legacy_balance,
       coalesce(t.entry_count,0) AS entry_count,coalesce(t.incomplete_count,0) AS incomplete_count,
       CASE WHEN coalesce(t.incomplete_count,0)=0 THEN coalesce(t.reconstructed_balance,0) END AS reconstructed_balance,
       coalesce(t.running_mismatch_count,0) AS running_mismatch_count,
       d.status AS decision_status,d.resolution,d.amount_override,d.rationale,d.evidence,
       CASE
         WHEN d.status='resolved' AND d.amount_override IS NOT NULL THEN d.amount_override
         WHEN a.legacy_balance IS NOT NULL AND coalesce(t.incomplete_count,0)=0
              AND coalesce(t.reconstructed_balance,0)=a.legacy_balance THEN a.legacy_balance
       END AS canonical_balance
FROM portfolio.account a
LEFT JOIN totals t ON t.batch_id=a.batch_id AND t.account_id=a.legacy_id
LEFT JOIN ledger.reconciliation_decision d
  ON d.batch_id=a.batch_id AND d.subject_type='account' AND d.subject_id=a.legacy_id;
