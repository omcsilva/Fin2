-- Expose ISO 4217 codes while preserving the original Fin1 payload verbatim.
CREATE OR REPLACE VIEW portfolio.currency AS
SELECT * REPLACE (
  CASE upper(abbreviation)
    WHEN 'REAL' THEN 'BRL'
    WHEN 'DOL' THEN 'USD'
    WHEN 'DOLAR' THEN 'USD'
    ELSE upper(abbreviation)
  END AS abbreviation
)
FROM portfolio.reference WHERE kind='moeda';

UPDATE ledger.manual_event SET currency=CASE upper(currency)
  WHEN 'REAL' THEN 'BRL' WHEN 'DOL' THEN 'USD' WHEN 'DOLAR' THEN 'USD'
  ELSE upper(currency) END;
UPDATE ledger.manual_transfer SET currency=CASE upper(currency)
  WHEN 'REAL' THEN 'BRL' WHEN 'DOL' THEN 'USD' WHEN 'DOLAR' THEN 'USD'
  ELSE upper(currency) END;
UPDATE ledger.statement_balance_observation SET currency=CASE upper(currency)
  WHEN 'REAL' THEN 'BRL' WHEN 'DOL' THEN 'USD' WHEN 'DOLAR' THEN 'USD'
  ELSE upper(currency) END;
UPDATE market.manual_price SET currency=CASE upper(currency)
  WHEN 'REAL' THEN 'BRL' WHEN 'DOL' THEN 'USD' WHEN 'DOLAR' THEN 'USD'
  ELSE upper(currency) END;
