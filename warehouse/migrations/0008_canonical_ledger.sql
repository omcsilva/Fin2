-- Canonical, source-backed ledger projections. Imported rows remain immutable.
CREATE SCHEMA ledger;

CREATE TABLE ledger.reconciliation_decision (
    decision_id VARCHAR PRIMARY KEY,
    batch_id VARCHAR NOT NULL,
    subject_type VARCHAR NOT NULL,
    subject_id BIGINT NOT NULL,
    status VARCHAR NOT NULL CHECK (status IN ('resolved','pending')),
    resolution VARCHAR NOT NULL,
    quantity_override DECIMAL(28,10),
    rationale VARCHAR NOT NULL,
    evidence JSON NOT NULL,
    decided_at TIMESTAMPTZ NOT NULL DEFAULT current_timestamp,
    UNIQUE(batch_id,subject_type,subject_id)
);

CREATE VIEW ledger.event AS
SELECT m.batch_id,m.source_record_id AS event_id,m.legacy_id AS legacy_event_id,
       m.application_id,a.account_id,m.cash_entry_id,m.operation_id,o.name AS operation,
       m.trade_date,m.settlement_date,
       CASE WHEN m.settlement_date IS NULL THEN 'planned' ELSE 'settled' END AS status,
       m.source_quantity,m.source_value
FROM portfolio.movement m
LEFT JOIN portfolio.application a ON a.batch_id=m.batch_id AND a.legacy_id=m.application_id
LEFT JOIN portfolio.operation o ON o.batch_id=m.batch_id AND o.legacy_id=m.operation_id;

CREATE VIEW ledger.position_component AS
SELECT e.batch_id,e.event_id,e.application_id,e.operation_id,
       abs(e.source_quantity)*o.quantity_multiplier AS signed_quantity,
       e.source_value AS source_value
FROM ledger.event e
LEFT JOIN portfolio.operation o ON o.batch_id=e.batch_id AND o.legacy_id=e.operation_id;

-- A linked cash entry is the authoritative cash component; it is not added to
-- movement values again. Unlinked entries remain visible as standalone events.
CREATE VIEW ledger.cash_component AS
SELECT c.batch_id,c.source_record_id AS cash_component_id,c.legacy_id AS legacy_cash_id,
       c.account_id,c.settlement_date,d.signed_value,d.description,
       m.source_record_id AS related_event_id
FROM portfolio.cash_entry c
JOIN portfolio.cash_detail d ON d.batch_id=c.batch_id AND d.legacy_id=c.legacy_id
LEFT JOIN portfolio.movement m ON m.batch_id=c.batch_id AND m.cash_entry_id=c.legacy_id;

CREATE VIEW ledger.position_reconciliation AS
SELECT q.*,
       d.status AS decision_status,d.resolution,d.quantity_override,d.rationale,d.evidence,
       CASE
         WHEN d.status='resolved' AND d.quantity_override IS NOT NULL THEN d.quantity_override
         WHEN q.legacy_delta=0 THEN q.all_settled_quantity
       END AS canonical_quantity
FROM portfolio.quantity_check q
LEFT JOIN ledger.reconciliation_decision d
  ON d.batch_id=q.batch_id AND d.subject_type='application' AND d.subject_id=q.application_id;
