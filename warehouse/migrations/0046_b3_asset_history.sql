CREATE TABLE market.b3_history_capture (
  capture_id VARCHAR PRIMARY KEY,
  provider VARCHAR NOT NULL CHECK(provider='b3_cotahist'),
  original_filename VARCHAR NOT NULL,
  captured_at TIMESTAMPTZ NOT NULL,
  response_sha256 VARCHAR NOT NULL UNIQUE,
  response_body BLOB NOT NULL
);

CREATE TABLE market.b3_daily_close (
  source_record_id VARCHAR NOT NULL,
  trading_date DATE NOT NULL,
  provider VARCHAR NOT NULL CHECK(provider='b3_cotahist'),
  currency VARCHAR NOT NULL CHECK(currency='BRL'),
  close DECIMAL(28,10) NOT NULL CHECK(close>0),
  adjusted_close DECIMAL(28,10),
  capture_id VARCHAR NOT NULL,
  captured_at TIMESTAMPTZ NOT NULL,
  PRIMARY KEY(source_record_id,trading_date,provider)
);

CREATE OR REPLACE VIEW market.daily_close_series AS
SELECT d.*,a.symbol,a.name
FROM market.daily_close d JOIN market.asset_catalog a ON a.source_record_id=d.source_record_id
UNION ALL
SELECT d.*,a.symbol,a.name
FROM market.b3_daily_close d JOIN market.asset_catalog a ON a.source_record_id=d.source_record_id;

CREATE OR REPLACE VIEW market.comparison_series AS
SELECT source_record_id AS series_id,symbol AS code,name,trading_date AS observation_date,
       coalesce(adjusted_close,close) AS value,
       CASE WHEN adjusted_close IS NULL THEN 'unadjusted_price' ELSE 'price' END AS unit,
       'daily' AS frequency,provider
FROM market.daily_close_series
UNION ALL
SELECT v.benchmark_source_record_id,c.abbreviation,c.name,v.observation_date,
       v.value,v.unit,v.frequency,v.provider
FROM market.benchmark_value v JOIN market.benchmark_catalog c
  ON c.source_record_id=v.benchmark_source_record_id;
