-- Exact decimal allocation: rounded shares plus the residual on the final row.
CREATE VIEW ledger.cash_flow_effective_v3 AS
WITH shares AS (
  SELECT v.*,e.signed_amount,
    CAST(round(v.amount,4) AS DECIMAL(28,4)) rounded_amount,
    row_number() OVER(PARTITION BY v.cash_component_id ORDER BY v.related_event_id NULLS LAST) allocation_number,
    count(*) OVER(PARTITION BY v.cash_component_id) allocation_count
  FROM ledger.cash_flow_effective_v2 v
  JOIN ledger.cash_entry_canonical e ON e.cash_entry_id=v.cash_component_id
), totals AS (
  SELECT *,sum(rounded_amount) OVER(PARTITION BY cash_component_id) rounded_total
  FROM shares
)
SELECT * EXCLUDE(amount,signed_amount,rounded_amount,allocation_number,allocation_count,rounded_total),
  CAST(CASE WHEN allocation_number=allocation_count
       THEN rounded_amount+(signed_amount-rounded_total)
       ELSE rounded_amount END AS DECIMAL(28,4)) amount
FROM totals;
