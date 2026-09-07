-- Corrections used only by cost-basis reconstruction. The imported movement
-- and ledger.event remain unchanged so their original semantics stay auditable.
CREATE TABLE ledger.cost_event_override (
    batch_id VARCHAR NOT NULL,
    legacy_movement_id BIGINT NOT NULL,
    operation_override VARCHAR,
    quantity_override DECIMAL(28,10),
    rationale VARCHAR NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT current_timestamp,
    PRIMARY KEY (batch_id, legacy_movement_id)
);

-- Duplicate of the JCP movement tied to the same legacy cash entry. Ignore it
-- only in cost reconstruction; do not relabel the source movement as income.
INSERT INTO ledger.cost_event_override
  (batch_id,legacy_movement_id,operation_override,quantity_override,rationale)
SELECT m.batch_id,m.legacy_id,'ignore',0,
       'Duplicata de JCP ligada ao lançamento 213; ignorada somente no custo médio'
FROM portfolio.movement m
WHERE m.source_record_id='3edcd8b0f76fb2ec72ad4cba5d6628559fad8fd0a15ba88c425324e3b8f9e7c1'
  AND m.legacy_id=3441
ON CONFLICT DO NOTHING;

-- Quantities verified in the corresponding XP brokerage notes.
INSERT INTO ledger.cost_event_override
  (batch_id,legacy_movement_id,operation_override,quantity_override,rationale)
SELECT m.batch_id,m.legacy_id,'Compra',100,
       '100 VALE3 a R$ 40,07; nota XP 20009637, pregão de 16/03/2020'
FROM portfolio.movement m
WHERE m.source_record_id='4f943c3a8759b2337c13a4062f6df42ce8cc076bfeeee3bd1f8b05d0b95065fb'
  AND m.legacy_id=5120
ON CONFLICT DO NOTHING;

INSERT INTO ledger.cost_event_override
  (batch_id,legacy_movement_id,operation_override,quantity_override,rationale)
SELECT m.batch_id,m.legacy_id,'Venda',-100,
       '100 VALE3 a R$ 43,54; nota XP 20508449, pregão de 01/04/2020'
FROM portfolio.movement m
WHERE m.source_record_id='efd1d0b9602b4dddf7021dd96f50feae2996499368820fcf96235aaa5be09085'
  AND m.legacy_id=5121
ON CONFLICT DO NOTHING;

INSERT INTO document_record_link (document_id,record_id,relation)
SELECT d.document_id,m.source_record_id,'evidence'
FROM source_document d CROSS JOIN portfolio.movement m
WHERE d.document_id='25e2cc8d55c94b776ef8b282ff307794899450a018d2aa0714a6e178edc6e499'
  AND m.source_record_id='4f943c3a8759b2337c13a4062f6df42ce8cc076bfeeee3bd1f8b05d0b95065fb'
ON CONFLICT DO NOTHING;

INSERT INTO document_record_link (document_id,record_id,relation)
SELECT d.document_id,m.source_record_id,'evidence'
FROM source_document d CROSS JOIN portfolio.movement m
WHERE d.document_id='92ce010a722b16475e42b180ad85fbc34636ecc02928e064ec1e4a8903a61993'
  AND m.source_record_id='efd1d0b9602b4dddf7021dd96f50feae2996499368820fcf96235aaa5be09085'
ON CONFLICT DO NOTHING;
