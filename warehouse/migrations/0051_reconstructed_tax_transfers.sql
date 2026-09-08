-- Full-position custody transfers with matching holder, asset, date and
-- quantity. Carry the source account's reconstructed tax cost; preserved
-- portfolio values differ and are intentionally not used as tax cost.
INSERT INTO ledger.cost_event_override
  (batch_id,legacy_movement_id,operation_override,quantity_override,rationale,amount_override)
SELECT m.batch_id,v.legacy_movement_id,v.operation_override,v.quantity_override,
       'Transferência integral pareada; custo fiscal reconstruído na origem e transportado sem venda. ' ||
       v.evidence,v.amount_override
FROM portfolio.movement m JOIN (VALUES
 (5016,'tax_transfer_out',290.0000000000,'BRCR11: saída XP para Warren em 21/11/2022',20147.7500000000),
 (3929,'tax_transfer_in',290.0000000000,'BRCR11: entrada Warren vinda da XP em 21/11/2022',20147.7500000000),
 (4596,'tax_transfer_out',351.0000000000,'DIVO11: saída Clear para XP em 07/08/2023',23190.6541522500),
 (4613,'tax_transfer_in',351.0000000000,'DIVO11: entrada XP vinda da Clear em 07/08/2023',23190.6541522500),
 (4597,'tax_transfer_out',400.0000000000,'ELET3: saída Clear para XP de Luciana em 07/08/2023',14144.2320000000),
 (4614,'tax_transfer_in',400.0000000000,'ELET3: entrada XP vinda da Clear de Luciana em 07/08/2023',14144.2320000000),
 (4599,'tax_transfer_out',77.0000000000,'KNRI11: saída Clear para XP em 07/08/2023',10020.0100000000),
 (4616,'tax_transfer_in',77.0000000000,'KNRI11: entrada XP vinda da Clear em 07/08/2023',10020.0100000000),
 (4602,'tax_transfer_out',9500.0000000000,'USIM3: saída Clear para XP de Luciana em 07/08/2023',77564.8210000000),
 (4619,'tax_transfer_in',9500.0000000000,'USIM3: entrada XP vinda da Clear de Luciana em 07/08/2023',77564.8210000000),
 (4603,'tax_transfer_out',1100.0000000000,'VALE3: saída Clear para XP de Luciana em 07/08/2023',53244.4911285714),
 (4620,'tax_transfer_in',1100.0000000000,'VALE3: entrada XP vinda da Clear de Luciana em 07/08/2023',53244.4911285714),
 (4649,'tax_transfer_out',3500.0000000000,'LIGT3: saída Clear para XP em 19/09/2023',13777.4572250000),
 (4659,'tax_transfer_in',3500.0000000000,'LIGT3: entrada XP vinda da Clear em 19/09/2023',13777.4572250000),
 (4987,'tax_transfer_out',100.0000000000,'ELET3: saída NuInvest para XP de Marcos em 25/03/2024',4175.9693617021),
 (4990,'tax_transfer_in',100.0000000000,'ELET3: entrada XP vinda da NuInvest de Marcos em 25/03/2024',4175.9693617021),
 (4988,'tax_transfer_out',3085.0000000000,'USIM3: saída NuInvest para XP de Marcos em 25/03/2024',24929.8492300000),
 (4992,'tax_transfer_in',3085.0000000000,'USIM3: entrada XP vinda da NuInvest de Marcos em 25/03/2024',24929.8492300000)
) v(legacy_movement_id,operation_override,quantity_override,evidence,amount_override)
ON v.legacy_movement_id=m.legacy_id;
