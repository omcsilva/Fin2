CREATE VIEW market.benchmark_catalog AS
SELECT source_record_id,batch_id,legacy_id,name,abbreviation,
       DATE '2000-01-01' AS start_date,
       CASE abbreviation WHEN 'CDI' THEN 'macro' WHEN 'SLC' THEN 'macro'
         WHEN 'INF' THEN 'macro' WHEN 'DOL' THEN 'currency'
         WHEN 'EUR' THEN 'currency' WHEN 'IBO' THEN 'stocks' END AS provider_family,
       CASE abbreviation WHEN 'CDI' THEN 'cdi' WHEN 'SLC' THEN 'selic'
         WHEN 'INF' THEN 'ipca' WHEN 'DOL' THEN 'USD-BRL'
         WHEN 'EUR' THEN 'EUR-BRL' WHEN 'IBO' THEN '^BVSP' END AS provider_symbol
FROM portfolio.reference
WHERE kind='indice' AND abbreviation IN ('CDI','SLC','INF','DOL','EUR','IBO');

CREATE TABLE market.benchmark_capture (
  capture_id VARCHAR PRIMARY KEY,provider VARCHAR NOT NULL,endpoint VARCHAR NOT NULL,
  requested_symbol VARCHAR NOT NULL,captured_at TIMESTAMPTZ NOT NULL,
  response_sha256 VARCHAR NOT NULL,response_body BLOB NOT NULL,
  UNIQUE(provider,response_sha256)
);

CREATE TABLE market.benchmark_value (
  benchmark_source_record_id VARCHAR NOT NULL,observation_date DATE NOT NULL,
  provider VARCHAR NOT NULL,provider_symbol VARCHAR NOT NULL,
  frequency VARCHAR NOT NULL,value DECIMAL(28,10) NOT NULL,
  unit VARCHAR NOT NULL,capture_id VARCHAR NOT NULL,captured_at TIMESTAMPTZ NOT NULL,
  PRIMARY KEY(benchmark_source_record_id,observation_date,provider)
);

CREATE VIEW market.comparison_series AS
SELECT source_record_id AS series_id,symbol AS code,name,trading_date AS observation_date,
       adjusted_close AS value,'price' AS unit,'daily' AS frequency,provider
FROM market.daily_close_series WHERE adjusted_close IS NOT NULL
UNION ALL
SELECT v.benchmark_source_record_id,c.abbreviation,c.name,v.observation_date,
       v.value,v.unit,v.frequency,v.provider
FROM market.benchmark_value v JOIN market.benchmark_catalog c
  ON c.source_record_id=v.benchmark_source_record_id;
