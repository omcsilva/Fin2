-- Daily closes are accepted market observations and must be available to
-- valuations at historical cutoffs, including dates before the latest quote.
CREATE OR REPLACE VIEW market.ledger_price_observation AS
SELECT source_record_id,price,currency,CAST(reference_date AS TIMESTAMPTZ) quoted_at,
       recorded_at captured_at,price_id capture_id,'manual' provider,source
FROM market.manual_price
UNION ALL
SELECT source_record_id,price,currency,quoted_at,queried_at,capture_id,'brapi_v2','brapi'
FROM market.asset_price_query_success
UNION ALL
SELECT source_record_id,coalesce(adjusted_close,close),currency,
       CAST(trading_date AS TIMESTAMPTZ),captured_at,capture_id,provider,provider
FROM market.daily_close_series
UNION ALL
SELECT source_record_id,legacy_price,currency,CAST(price_date AS TIMESTAMPTZ),
       TIMESTAMPTZ '1970-01-01 00:00:00+00',source_record_id,'fin1_snapshot','Referência importada'
FROM market.asset_catalog_effective WHERE legacy_price>0 AND price_date IS NOT NULL;

