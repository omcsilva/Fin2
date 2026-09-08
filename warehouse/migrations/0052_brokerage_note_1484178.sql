-- Brokerage note 1484178 proves gross sales of BRL 40,285.00 ITAUSA and
-- BRL 2,518.00 PETR4, with BRL 42,787.37 net proceeds. Allocate the net in
-- exact gross-value proportion; the PETR4 acquisition provenance remains open.
INSERT INTO ledger.cost_event_override
  (batch_id,legacy_movement_id,operation_override,quantity_override,rationale,amount_override)
SELECT m.batch_id,m.legacy_id,v.operation_override,v.quantity_override,v.rationale,v.amount_override
FROM portfolio.movement m JOIN (VALUES
 (3244,NULL,NULL,'Líquido rateado da venda ITAUSA; nota Clear 1484178 de 09/11/2018',40270.2894762049),
 (3245,'Venda',-100.0000000000,'Venda de 100 PETR4 a R$ 25,18; nota Clear 1484178 de 09/11/2018',2517.0805237951)
) v(legacy_movement_id,operation_override,quantity_override,rationale,amount_override)
ON v.legacy_movement_id=m.legacy_id;
