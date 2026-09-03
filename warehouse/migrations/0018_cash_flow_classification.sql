-- Auditable cash-flow classification. Source rows remain immutable.
CREATE VIEW ledger.cash_flow_classification AS
WITH base AS (
  SELECT c.batch_id,c.cash_component_id,c.legacy_cash_id,c.account_id,
    c.settlement_date,c.signed_value AS amount,c.description,c.related_event_id,
    cur.abbreviation AS currency,m.application_id,o.name AS operation,
    upper(coalesce(c.description,'')) AS normalized_description,
    CASE WHEN upper(coalesce(c.description,'')) LIKE '%TED%'
           OR upper(coalesce(c.description,'')) LIKE '%TRANSFER%'
           OR upper(coalesce(c.description,'')) LIKE '%DEP_SITO%'
           OR upper(coalesce(c.description,'')) LIKE '%SAQUE%'
           OR upper(coalesce(c.description,'')) LIKE '%RETIRADA EM C/C%'
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
)
SELECT * EXCLUDE(normalized_description,transfer_candidate,positive_matches,negative_matches),
  CASE
    WHEN related_event_id IS NOT NULL AND lower(coalesce(operation,'')) IN ('rendimento','dividendo','juros c p') THEN 'income'
    WHEN related_event_id IS NOT NULL AND lower(coalesce(operation,'')) IN ('imposto','come-cotas') THEN 'tax'
    WHEN related_event_id IS NOT NULL AND lower(coalesce(operation,''))='taxa' THEN 'fee'
    WHEN related_event_id IS NOT NULL THEN 'investment'
    WHEN normalized_description LIKE '%RENDIMENTO%' OR normalized_description LIKE '%DIVIDEND%'
      OR normalized_description LIKE '%JUROS%' OR normalized_description LIKE '%INTEREST%'
      OR normalized_description LIKE '%REMUNERA%BTC%' THEN 'income'
    WHEN normalized_description LIKE '%IRRF%' OR normalized_description LIKE '%IMPOSTO%'
      OR normalized_description LIKE '%TAX ADJ%' THEN 'tax'
    WHEN normalized_description LIKE '%TAXA%' OR normalized_description LIKE '%MULTA%'
      OR normalized_description LIKE '%FEE%' THEN 'fee'
    WHEN transfer_candidate AND positive_matches>0 AND negative_matches>0 THEN 'internal_transfer'
    WHEN transfer_candidate AND amount>0 THEN 'external_contribution'
    WHEN transfer_candidate AND amount<0 THEN 'external_withdrawal'
    ELSE 'unclassified'
  END AS category,
  CASE
    WHEN related_event_id IS NOT NULL THEN 'source_link'
    WHEN transfer_candidate AND positive_matches>0 AND negative_matches>0 THEN 'matched_date_currency_amount'
    WHEN transfer_candidate THEN 'description_pattern'
    WHEN normalized_description LIKE '%RENDIMENTO%' OR normalized_description LIKE '%DIVIDEND%'
      OR normalized_description LIKE '%JUROS%' OR normalized_description LIKE '%INTEREST%'
      OR normalized_description LIKE '%REMUNERA%BTC%' OR normalized_description LIKE '%IRRF%'
      OR normalized_description LIKE '%IMPOSTO%' OR normalized_description LIKE '%TAX ADJ%'
      OR normalized_description LIKE '%TAXA%' OR normalized_description LIKE '%MULTA%'
      OR normalized_description LIKE '%FEE%' THEN 'description_pattern'
    ELSE 'none'
  END AS classification_basis
FROM paired;
