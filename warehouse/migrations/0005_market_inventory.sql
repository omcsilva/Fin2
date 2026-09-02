-- Snapshot observations, not verified canonical identities or live market data.
CREATE SCHEMA market;

CREATE VIEW market.asset_catalog AS
SELECT a.*,c.abbreviation AS currency,
       json_extract_string(r.payload,'$.codigo') AS legacy_code,
       json_extract_string(r.payload,'$.cnpj') AS legacy_cnpj,
       json_extract_string(r.payload,'$.dt_cotacao') AS source_price_timestamp,
       w.record_id AS provider_record_id,
       json_extract_string(w.payload,'$.plugin') AS configured_provider,
       json_extract_string(w.payload,'$.multiplicador') AS configured_multiplier
FROM portfolio.asset a JOIN source_record r ON r.record_id=a.source_record_id
LEFT JOIN portfolio.currency c ON c.batch_id=a.batch_id AND c.legacy_id=a.currency_id
LEFT JOIN source_record w ON w.batch_id=a.batch_id AND w.database_name='db.sqlite3'
    AND w.table_name='fin1_webscrap'
    AND w.legacy_id=CAST(json_extract_string(r.payload,'$.webscrap_id') AS BIGINT);

CREATE VIEW market.identifier_candidate AS
WITH candidates AS (
    SELECT batch_id,source_record_id,legacy_id,'abrev' AS source_field,symbol AS raw_value FROM market.asset_catalog
    UNION ALL
    SELECT batch_id,source_record_id,legacy_id,'codigo',legacy_code FROM market.asset_catalog
    UNION ALL
    SELECT batch_id,source_record_id,legacy_id,'cnpj',legacy_cnpj FROM market.asset_catalog
)
SELECT *,count(*) OVER(PARTITION BY batch_id,source_field,trim(raw_value)) AS occurrences,
       'unverified' AS verification_status
FROM candidates WHERE nullif(trim(raw_value),'') IS NOT NULL;

CREATE VIEW market.price_observation AS
SELECT a.batch_id,a.source_record_id AS observation_id,a.source_record_id,
       a.legacy_id AS asset_id,a.name,a.symbol,a.currency,
       a.legacy_price AS price,a.price_date,a.source_price_timestamp,
       'fin1_snapshot' AS source,a.configured_provider,a.provider_record_id,
       b.imported_at AS captured_at,b.as_of_date,
       date_diff('day',a.price_date,b.as_of_date) AS age_at_cutoff_days,
       CASE WHEN a.legacy_price IS NULL THEN 'missing_price'
            WHEN a.legacy_price<=0 THEN 'invalid_price'
            WHEN nullif(trim(a.currency),'') IS NULL THEN 'missing_currency'
            WHEN a.price_date IS NULL THEN 'missing_date'
            WHEN a.price_date>b.as_of_date THEN 'future_price'
            WHEN date_diff('day',a.price_date,b.as_of_date)>30 THEN 'stale_price'
            ELSE 'available' END AS quality
FROM market.asset_catalog a JOIN import_batch b USING(batch_id);
