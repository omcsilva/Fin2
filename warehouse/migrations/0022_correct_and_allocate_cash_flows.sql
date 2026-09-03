-- Canonical sign and one proportional allocation per linked movement. This
-- prevents a brokerage-note cash total from being counted once per asset.
CREATE VIEW ledger.cash_flow_effective_v2 AS
WITH latest AS (
  SELECT * FROM ledger.cash_flow_decision
  QUALIFY row_number() OVER(PARTITION BY cash_component_id ORDER BY decided_at DESC,decision_id DESC)=1
), rules AS (
  SELECT cash_component_id,any_value(category) category,any_value(classification_basis) classification_basis
  FROM ledger.cash_flow_classification_final GROUP BY cash_component_id
), linked AS (
  SELECT e.batch_id,e.cash_entry_id AS cash_component_id,e.legacy_id AS legacy_cash_id,
    e.account_id,e.settlement_date,e.signed_amount,e.description,cur.abbreviation currency,
    m.source_record_id AS related_event_id,m.application_id,o.name operation,
    abs(m.source_value) allocation_weight,
    sum(abs(m.source_value)) OVER(PARTITION BY e.cash_entry_id) total_weight
  FROM ledger.cash_entry_canonical e
  LEFT JOIN portfolio.account a ON a.batch_id=e.batch_id AND a.legacy_id=e.account_id
  LEFT JOIN portfolio.currency cur ON cur.batch_id=a.batch_id AND cur.legacy_id=a.currency_id
  LEFT JOIN portfolio.movement m ON m.batch_id=e.batch_id AND m.cash_entry_id=e.legacy_id
  LEFT JOIN portfolio.operation o ON o.batch_id=m.batch_id AND o.legacy_id=m.operation_id
  WHERE e.account_id IS NOT NULL AND e.signed_amount IS NOT NULL
)
SELECT l.* EXCLUDE(signed_amount,allocation_weight,total_weight),
  CASE WHEN related_event_id IS NULL OR coalesce(total_weight,0)=0 THEN signed_amount
       ELSE signed_amount*allocation_weight/total_weight END AS amount,
  coalesce(d.category,
    CASE WHEN related_event_id IS NOT NULL AND lower(coalesce(operation,'')) IN ('rendimento','dividendo','juros c p') THEN 'income'
         WHEN related_event_id IS NOT NULL AND lower(coalesce(operation,'')) IN ('imposto','come-cotas') THEN 'tax'
         WHEN related_event_id IS NOT NULL AND lower(coalesce(operation,''))='taxa' THEN 'fee'
         WHEN related_event_id IS NOT NULL THEN 'investment'
         WHEN r.category='external_contribution' AND signed_amount<0 THEN 'external_withdrawal'
         WHEN r.category='external_withdrawal' AND signed_amount>0 THEN 'external_contribution'
         ELSE r.category END) category,
  CASE WHEN d.decision_id IS NOT NULL THEN 'manual_decision'
       WHEN related_event_id IS NOT NULL THEN 'source_link_allocated'
       ELSE r.classification_basis END classification_basis,
  d.decision_id,d.rationale,d.decided_at
FROM linked l
LEFT JOIN rules r USING(cash_component_id)
LEFT JOIN latest d USING(cash_component_id);
