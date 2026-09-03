-- Refine high-confidence patterns found during review of unclassified rows.
CREATE OR REPLACE VIEW ledger.cash_flow_classification AS
WITH base AS (
  SELECT c.batch_id,c.cash_component_id,c.legacy_cash_id,c.account_id,
    c.settlement_date,c.signed_value AS amount,c.description,c.related_event_id,
    cur.abbreviation AS currency,m.application_id,o.name AS operation,
    upper(coalesce(c.description,'')) AS normalized_description,
    CASE WHEN upper(coalesce(c.description,'')) LIKE '%TED%'
           OR upper(coalesce(c.description,'')) LIKE '%TRANSFER%'
           OR upper(coalesce(c.description,'')) LIKE '%TRANSF.%'
           OR upper(coalesce(c.description,'')) LIKE '%DEP_SITO%'
           OR upper(coalesce(c.description,'')) LIKE '%SAQUE%'
           OR upper(coalesce(c.description,'')) LIKE '%RETIRADA%'
           OR upper(coalesce(c.description,'')) LIKE '%WIRE RECEIVED%'
           OR upper(coalesce(c.description,'')) LIKE '%MONEYLINK DEPOSIT%'
         THEN true ELSE false END AS transfer_candidate
  FROM ledger.cash_component c
  LEFT JOIN portfolio.account a ON a.batch_id=c.batch_id AND a.legacy_id=c.account_id
  LEFT JOIN portfolio.currency cur ON cur.batch_id=a.batch_id AND cur.legacy_id=a.currency_id
  LEFT JOIN portfolio.movement m ON m.source_record_id=c.related_event_id
  LEFT JOIN portfolio.operation o ON o.batch_id=m.batch_id AND o.legacy_id=m.operation_id
  WHERE c.account_id IS NOT NULL AND c.signed_value IS NOT NULL
), paired AS (
  SELECT b.*,
    count(*) FILTER(WHERE amount>0) OVER(PARTITION BY batch_id,settlement_date,currency,abs(amount)) positive_matches,
    count(*) FILTER(WHERE amount<0) OVER(PARTITION BY batch_id,settlement_date,currency,abs(amount)) negative_matches
  FROM base b
), classified AS (
SELECT *,
  CASE
    WHEN related_event_id IS NOT NULL AND lower(coalesce(operation,'')) IN ('rendimento','dividendo','juros c p') THEN 'income'
    WHEN related_event_id IS NOT NULL AND lower(coalesce(operation,'')) IN ('imposto','come-cotas') THEN 'tax'
    WHEN related_event_id IS NOT NULL AND lower(coalesce(operation,''))='taxa' THEN 'fee'
    WHEN related_event_id IS NOT NULL THEN 'investment'
    WHEN normalized_description LIKE '%RENDIMENTO%' OR normalized_description LIKE '%DIVIDEND%'
      OR normalized_description LIKE '%JUROS%' OR normalized_description LIKE '%INTEREST%'
      OR normalized_description LIKE '%REMUNERA%BTC%' THEN 'income'
    WHEN normalized_description LIKE '%IRRF%' OR normalized_description LIKE 'IR %'
      OR normalized_description LIKE '%IMPOSTO%' OR normalized_description LIKE '%IOF%'
      OR normalized_description LIKE '%TAX ADJ%' OR normalized_description LIKE '%FOREIGN TAX%' THEN 'tax'
    WHEN normalized_description LIKE '%TAXA%' OR normalized_description LIKE '%MULTA%'
      OR normalized_description LIKE '%FEE%' OR normalized_description LIKE '%NELOGICA%' THEN 'fee'
    WHEN transfer_candidate AND positive_matches>0 AND negative_matches>0 THEN 'internal_transfer'
    WHEN transfer_candidate AND amount>0 THEN 'external_contribution'
    WHEN transfer_candidate AND amount<0 THEN 'external_withdrawal'
    WHEN normalized_description LIKE 'COMPRA %' OR normalized_description LIKE 'VENDA %'
      OR normalized_description LIKE 'BUY %' OR normalized_description LIKE 'RESGATE %'
      OR normalized_description LIKE 'LIQUIDA__O %' OR normalized_description LIKE 'OPERA__ES EM BOLSA%'
      OR normalized_description LIKE '%NOTA%PREG_O%'
      OR normalized_description LIKE '%CAMBIO %INTERN%'
      OR normalized_description LIKE '%RECOMPRA%' OR normalized_description LIKE '%SUBSCRI__O%'
      OR normalized_description LIKE '%ESTORNO%COMPRAS%'
      OR normalized_description LIKE '%REGULARIZA__O DA COMPRA%'
      OR normalized_description LIKE '%REEMBOLSO DE EVENTO%'
      OR normalized_description LIKE '%FRA__ES DE A__ES%'
      OR normalized_description LIKE '%PAGAMENTO DE RESGATE%'
      OR normalized_description LIKE '%AJUSTE DE POSI__O%'
      OR normalized_description LIKE '%VIA PORTABILIDADE%' THEN 'investment'
    ELSE 'unclassified'
  END AS category
FROM paired)
SELECT * EXCLUDE(normalized_description,transfer_candidate,positive_matches,negative_matches),
  CASE WHEN related_event_id IS NOT NULL THEN 'source_link'
       WHEN category='internal_transfer' THEN 'matched_date_currency_amount'
       WHEN category<>'unclassified' THEN 'description_pattern'
       ELSE 'none' END AS classification_basis
FROM classified;
