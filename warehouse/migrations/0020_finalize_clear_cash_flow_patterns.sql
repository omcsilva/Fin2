-- Final clear patterns from the second exception review.
CREATE VIEW ledger.cash_flow_classification_final AS
SELECT * EXCLUDE(category,classification_basis),
  CASE
    WHEN upper(coalesce(description,'')) LIKE 'ACORDO COMERCIAL %' THEN 'income'
    WHEN upper(coalesce(description,'')) LIKE 'D_ZIMO%' AND amount>0 THEN 'external_contribution'
    WHEN upper(coalesce(description,'')) LIKE 'D_ZIMO%' AND amount<0 THEN 'external_withdrawal'
    WHEN upper(coalesce(description,'')) LIKE '%PARA A CONTA DO NUBANK%' THEN 'external_withdrawal'
    ELSE category
  END AS category,
  CASE
    WHEN upper(coalesce(description,'')) LIKE 'ACORDO COMERCIAL %'
      OR upper(coalesce(description,'')) LIKE 'D_ZIMO%'
      OR upper(coalesce(description,'')) LIKE '%PARA A CONTA DO NUBANK%'
      THEN 'description_pattern'
    ELSE classification_basis
  END AS classification_basis
FROM ledger.cash_flow_classification;
