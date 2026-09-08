ALTER TABLE ledger.cost_event_override ADD COLUMN amount_override DECIMAL(28,10);

-- Custody transfers whose source quantity and reconstructed source cost match
-- exactly. The outgoing and incoming legs carry cost without creating a sale.
INSERT INTO ledger.cost_event_override
  (batch_id,legacy_movement_id,operation_override,quantity_override,rationale,amount_override)
SELECT m.batch_id,v.legacy_movement_id,v.operation_override,v.quantity_override,
       'Transferência de custódia pareada; custo reconstruído na origem coincide com a saída preservada. ' ||
       v.evidence,v.amount_override
FROM portfolio.movement m JOIN (VALUES
 (5034,'tax_transfer_out',190.0000000000,'XPML11: saída XP para Warren em 21/11/2022',20064.0000000000),
 (3931,'tax_transfer_in',190.0000000000,'XPML11: entrada Warren vinda da XP em 21/11/2022',20064.0000000000),
 (5026,'tax_transfer_out',131.0000000000,'KNRI11: saída XP para Warren em 21/11/2022',19974.8800000000),
 (3932,'tax_transfer_in',131.0000000000,'KNRI11: entrada Warren vinda da XP em 21/11/2022',19974.8800000000),
 (5030,'tax_transfer_out',255.0000000000,'LUGG11: saída XP para Warren em 21/11/2022',20030.2500000000),
 (3947,'tax_transfer_in',255.0000000000,'LUGG11: entrada Warren vinda da XP em 21/11/2022',20030.2500000000),
 (5010,'tax_transfer_out',1100.0000000000,'BBDC4: saída XP para Warren em 21/11/2022',21813.0000000000),
 (3954,'tax_transfer_in',1100.0000000000,'BBDC4: entrada Warren vinda da XP em 21/11/2022',21813.0000000000),
 (5012,'tax_transfer_out',726.0000000000,'BERK34: saída XP para Warren em 21/11/2022',50014.1400000000),
 (3953,'tax_transfer_in',726.0000000000,'BERK34: entrada Warren vinda da XP em 21/11/2022',50014.1400000000),
 (5022,'tax_transfer_out',170.0000000000,'GGRC11: saída XP para Warren em 21/11/2022',19995.9000000000),
 (3946,'tax_transfer_in',5.0000000000,'GGRC11: primeira entrada Warren vinda da XP em 21/11/2022',591.9000000000),
 (3948,'tax_transfer_in',2.0000000000,'GGRC11: segunda entrada Warren vinda da XP em 21/11/2022',235.2000000000),
 (3949,'tax_transfer_in',163.0000000000,'GGRC11: terceira entrada Warren vinda da XP em 21/11/2022',19168.8000000000),
 (4595,'tax_transfer_out',130.0000000000,'BBPO11: saída Clear para XP em 07/08/2023',10398.7000000000),
 (4612,'tax_transfer_in',130.0000000000,'BBPO11: entrada XP vinda da Clear em 07/08/2023',10398.7000000000),
 (4598,'tax_transfer_out',100.0000000000,'GGRC11: saída Clear para XP em 07/08/2023',10499.0000000000),
 (4615,'tax_transfer_in',100.0000000000,'GGRC11: entrada XP vinda da Clear em 07/08/2023',10499.0000000000),
 (4600,'tax_transfer_out',150.0000000000,'LUGG11: saída Clear para XP em 07/08/2023',12120.0000000000),
 (4617,'tax_transfer_in',150.0000000000,'LUGG11: entrada XP vinda da Clear em 07/08/2023',12120.0000000000),
 (4601,'tax_transfer_out',700.0000000000,'SANB11: saída Clear para XP em 07/08/2023',19740.0000000000),
 (4618,'tax_transfer_in',700.0000000000,'SANB11: entrada XP vinda da Clear em 07/08/2023',19740.0000000000),
 (4648,'tax_transfer_out',500.0000000000,'ELET3: saída Clear para XP em 19/09/2023',20290.0000000000),
 (4660,'tax_transfer_in',500.0000000000,'ELET3: entrada XP vinda da Clear em 19/09/2023',20290.0000000000)
 ) v(legacy_movement_id,operation_override,quantity_override,evidence,amount_override)
 ON v.legacy_movement_id=m.legacy_id;
