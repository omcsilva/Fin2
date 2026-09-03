CREATE VIEW ledger.cash_dashboard AS
WITH totals AS (
  SELECT e.batch_id,e.account_id,count(*) AS entry_count,
         count(*) FILTER (WHERE e.signed_amount IS NULL) AS incomplete_count,
         count(*) FILTER (WHERE e.settlement_date IS NULL) AS undated_count,
         count(*) FILTER (WHERE e.settlement_date>b.as_of_date) AS future_count,
         count(*) FILTER (WHERE e.reconstructed_running_balance<>e.legacy_running_balance) AS running_mismatch_count,
         sum(e.signed_amount) AS reconstructed_balance,
         sum(e.signed_amount) FILTER (WHERE e.settlement_date<=b.as_of_date) AS balance_at_cutoff
  FROM ledger.cash_entry_canonical e JOIN import_batch b USING(batch_id)
  WHERE e.account_id IS NOT NULL GROUP BY e.batch_id,e.account_id
)
SELECT r.*,r.account_id AS legacy_id,a.currency_id,c.abbreviation AS currency,i.name AS investor_name,
       coalesce(t.undated_count,0) AS undated_count,coalesce(t.future_count,0) AS future_count,
       t.balance_at_cutoff,
       CASE WHEN r.legacy_balance IS NOT NULL THEN r.reconstructed_balance-r.legacy_balance END AS legacy_delta
FROM ledger.cash_account_reconciliation r
JOIN portfolio.account a ON a.batch_id=r.batch_id AND a.legacy_id=r.account_id
LEFT JOIN portfolio.currency c ON c.batch_id=a.batch_id AND c.legacy_id=a.currency_id
LEFT JOIN portfolio.investor i ON i.batch_id=a.batch_id AND i.legacy_id=a.investor_id
LEFT JOIN totals t ON t.batch_id=r.batch_id AND t.account_id=r.account_id;

CREATE VIEW ledger.cash_entry_dashboard AS
SELECT *,cash_entry_id AS source_record_id,signed_amount AS signed_value,
       reconstructed_running_balance-legacy_running_balance AS running_delta,
       CAST(settlement_date AS TIMESTAMP) AS settlement_timestamp
FROM ledger.cash_entry_canonical;
