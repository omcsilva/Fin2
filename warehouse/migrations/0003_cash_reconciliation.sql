-- Reconstruct the legacy cash convention; never add investment movements again.
CREATE VIEW portfolio.cash_detail AS
WITH normalized AS (
    SELECT e.*,CAST(json_extract_string(s.payload,'$.saldo') AS DECIMAL(28,4)) AS legacy_running_balance,
           CAST(json_extract_string(s.payload,'$.dtliq') AS TIMESTAMP) AS settlement_timestamp,
           json_extract_string(s.payload,'$.descricao') AS description,
           CASE WHEN e.is_credit THEN abs(e.source_value) WHEN NOT e.is_credit THEN -abs(e.source_value) END AS signed_value
    FROM portfolio.cash_entry e JOIN source_record s ON s.record_id=e.source_record_id
), running AS (
    SELECT *,
           sum(signed_value) OVER w AS partial_running_balance,
           count(*) FILTER (WHERE signed_value IS NULL) OVER w AS unknown_values
    FROM normalized
    WINDOW w AS (PARTITION BY batch_id,account_id ORDER BY settlement_timestamp NULLS FIRST,legacy_id ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)
)
SELECT *,CASE WHEN account_id IS NOT NULL AND unknown_values=0 THEN partial_running_balance END AS reconstructed_running_balance,
       CASE WHEN account_id IS NOT NULL AND unknown_values=0 THEN partial_running_balance-legacy_running_balance END AS running_delta
FROM running;

CREATE VIEW portfolio.cash_check AS
WITH totals AS (
    SELECT d.batch_id,d.account_id,count(*) AS entry_count,
           count(*) FILTER (WHERE signed_value IS NULL) AS incomplete_count,
           count(*) FILTER (WHERE settlement_date IS NULL) AS undated_count,
           count(*) FILTER (WHERE settlement_date>b.as_of_date) AS future_count,
           count(*) FILTER (WHERE signed_value<>source_value) AS sign_mismatch_count,
           count(*) FILTER (WHERE running_delta<>0) AS running_mismatch_count,
           sum(signed_value) AS all_balance,
           sum(signed_value) FILTER (WHERE settlement_date<=b.as_of_date) AS cutoff_balance
    FROM portfolio.cash_detail d JOIN import_batch b USING(batch_id)
    GROUP BY d.batch_id,d.account_id
)
SELECT a.*,c.abbreviation AS currency,i.name AS investor_name,
       coalesce(t.entry_count,0) AS entry_count,coalesce(t.incomplete_count,0) AS incomplete_count,
       coalesce(t.undated_count,0) AS undated_count,coalesce(t.future_count,0) AS future_count,
       coalesce(t.sign_mismatch_count,0) AS sign_mismatch_count,
       coalesce(t.running_mismatch_count,0) AS running_mismatch_count,
       CASE WHEN coalesce(t.incomplete_count,0)=0 THEN coalesce(t.all_balance,0) END AS reconstructed_balance,
       CASE WHEN coalesce(t.incomplete_count,0)=0 AND coalesce(t.undated_count,0)=0 THEN coalesce(t.cutoff_balance,0) END AS balance_at_cutoff,
       CASE WHEN coalesce(t.incomplete_count,0)=0 THEN coalesce(t.all_balance,0)-a.legacy_balance END AS legacy_delta
FROM portfolio.account a
LEFT JOIN totals t ON t.batch_id=a.batch_id AND t.account_id=a.legacy_id
LEFT JOIN portfolio.currency c ON c.batch_id=a.batch_id AND c.legacy_id=a.currency_id
LEFT JOIN portfolio.investor i ON i.batch_id=a.batch_id AND i.legacy_id=a.investor_id;

CREATE VIEW portfolio.quantity_detail AS
SELECT m.*,o.name AS operation_name,o.quantity_multiplier,
       abs(m.source_quantity)*o.quantity_multiplier AS signed_quantity,
       CAST(json_extract_string(s.payload,'$.em_carteira') AS DECIMAL(28,10)) AS legacy_running_quantity,
       json_extract_string(s.payload,'$.descricao') AS description
FROM portfolio.movement m
LEFT JOIN portfolio.operation o ON o.batch_id=m.batch_id AND o.legacy_id=m.operation_id
JOIN source_record s ON s.record_id=m.source_record_id;
