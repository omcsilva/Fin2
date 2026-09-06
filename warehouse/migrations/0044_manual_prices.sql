-- Include assets created in Fin2 in the quote catalog.
CREATE OR REPLACE VIEW market.asset_catalog AS
SELECT a.*,c.abbreviation AS currency,
       json_extract_string(r.payload,'$.codigo') AS legacy_code,
       json_extract_string(r.payload,'$.cnpj') AS legacy_cnpj,
       json_extract_string(r.payload,'$.dt_cotacao') AS source_price_timestamp,
       w.record_id AS provider_record_id,
       json_extract_string(w.payload,'$.plugin') AS configured_provider,
       json_extract_string(w.payload,'$.multiplicador') AS configured_multiplier
FROM portfolio.asset a JOIN catalog.effective_record r ON r.record_id=a.source_record_id
LEFT JOIN portfolio.currency c ON c.batch_id=a.batch_id AND c.legacy_id=a.currency_id
LEFT JOIN source_record w ON w.batch_id=a.batch_id AND w.database_name='db.sqlite3'
    AND w.table_name='fin1_webscrap'
    AND w.legacy_id=CAST(json_extract_string(r.payload,'$.webscrap_id') AS BIGINT);

CREATE TABLE market.manual_price (
  price_id VARCHAR PRIMARY KEY,
  source_record_id VARCHAR NOT NULL,
  price DECIMAL(28,10) NOT NULL CHECK(price>0),
  currency VARCHAR NOT NULL,
  reference_date DATE NOT NULL,
  source VARCHAR NOT NULL,
  note VARCHAR NOT NULL DEFAULT '',
  document_id VARCHAR,
  request_key VARCHAR NOT NULL UNIQUE,
  recorded_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE VIEW market.ledger_price_observation AS
SELECT source_record_id,price,currency,CAST(reference_date AS TIMESTAMPTZ) quoted_at,
       recorded_at captured_at,price_id capture_id,'manual' provider,source
FROM market.manual_price
UNION ALL
SELECT source_record_id,price,currency,quoted_at,queried_at,capture_id,'brapi_v2','brapi'
FROM market.asset_price_query_success
UNION ALL
SELECT source_record_id,legacy_price,currency,CAST(price_date AS TIMESTAMPTZ),
       TIMESTAMPTZ '1970-01-01 00:00:00+00',source_record_id,'fin1_snapshot','Referência importada'
FROM market.asset_catalog_effective WHERE legacy_price>0 AND price_date IS NOT NULL;

CREATE VIEW market.latest_ledger_price AS
SELECT * EXCLUDE(rank) FROM (
 SELECT *,row_number() OVER(PARTITION BY source_record_id
   ORDER BY CAST(quoted_at AS DATE) DESC,captured_at DESC,capture_id DESC) rank
 FROM market.ledger_price_observation WHERE CAST(quoted_at AS DATE)<=current_date
) WHERE rank=1;
