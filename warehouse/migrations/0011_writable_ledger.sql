CREATE TABLE ledger.manual_event (
    event_id VARCHAR PRIMARY KEY,
    account_source_record_id VARCHAR NOT NULL,
    application_source_record_id VARCHAR,
    event_type VARCHAR NOT NULL CHECK (event_type IN
      ('deposit','withdrawal','buy','sell','income','fee','tax','adjustment')),
    trade_date DATE,
    settlement_date DATE NOT NULL,
    currency VARCHAR NOT NULL,
    quantity DECIMAL(28,10),
    amount DECIMAL(28,4) NOT NULL,
    description VARCHAR NOT NULL,
    reverses_event_id VARCHAR,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (length(trim(description))>0),
    CHECK (quantity IS NULL OR quantity>=0),
    CHECK (reverses_event_id IS NULL OR reverses_event_id<>event_id)
);

CREATE TABLE ledger.audit_log (
    audit_id VARCHAR PRIMARY KEY,
    entity_type VARCHAR NOT NULL,
    entity_id VARCHAR NOT NULL,
    action VARCHAR NOT NULL CHECK (action IN ('create','reverse')),
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    payload JSON NOT NULL
);

CREATE VIEW ledger.all_event AS
SELECT event_id,'fin1' AS origin,operation AS event_type,trade_date,settlement_date,
       account_id,application_id,source_quantity,source_value,NULL AS currency,
       NULL AS description
FROM ledger.event
UNION ALL
SELECT event_id,'manual',event_type,trade_date,settlement_date,
       a.legacy_id,ap.legacy_id,quantity,amount,m.currency,m.description
FROM ledger.manual_event m
LEFT JOIN portfolio.account a ON a.source_record_id=m.account_source_record_id
LEFT JOIN portfolio.application ap ON ap.source_record_id=m.application_source_record_id;
