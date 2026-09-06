-- One logical counterparty for all flows between the investor and the ledger.
-- Original accounts and source evidence remain intact.
CREATE VIEW ledger.current_account_entry AS
SELECT 'current_account' AS account_key, batch_id, cash_component_id AS entry_id,
       settlement_date, currency, amount, category, NULL::DATE AS reversed_at
FROM ledger.cash_flow_effective_v3
WHERE category IN ('external_contribution', 'external_withdrawal', 'unclassified')
UNION ALL
SELECT 'current_account', a.batch_id, me.event_id, me.settlement_date, me.currency, me.amount,
       CASE event_type WHEN 'deposit' THEN 'external_contribution'
                       WHEN 'withdrawal' THEN 'external_withdrawal'
                       ELSE 'unclassified' END,
       (SELECT min(r.settlement_date) FROM ledger.manual_event r WHERE r.reverses_event_id=me.event_id)
FROM ledger.manual_event me
JOIN portfolio.account a ON a.source_record_id=me.account_source_record_id
WHERE me.transfer_id IS NULL AND me.reverses_event_id IS NULL
  AND event_type IN ('deposit', 'withdrawal', 'adjustment');
