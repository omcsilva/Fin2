CREATE TABLE ledger.cash_flow_decision (
  decision_id VARCHAR PRIMARY KEY,
  cash_component_id VARCHAR NOT NULL,
  category VARCHAR NOT NULL CHECK(category IN
    ('external_contribution','external_withdrawal','income','fee','tax','investment','internal_transfer')),
  rationale VARCHAR NOT NULL,
  decided_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK(length(trim(rationale))>=5)
);

CREATE VIEW ledger.cash_flow_effective AS
WITH latest AS (
  SELECT * FROM ledger.cash_flow_decision
  QUALIFY row_number() OVER(PARTITION BY cash_component_id ORDER BY decided_at DESC,decision_id DESC)=1
)
SELECT f.* EXCLUDE(category,classification_basis),
  coalesce(d.category,f.category) category,
  CASE WHEN d.decision_id IS NOT NULL THEN 'manual_decision' ELSE f.classification_basis END classification_basis,
  d.decision_id,d.rationale,d.decided_at
FROM ledger.cash_flow_classification_final f
LEFT JOIN latest d USING(cash_component_id);
