CREATE VIEW market.benchmark_value_effective AS
SELECT * EXCLUDE(priority,rank) FROM (
  SELECT v.*,
    CASE provider WHEN 'b3_index' THEN 1 WHEN 'bcb_sgs' THEN 2 ELSE 3 END priority,
    row_number() OVER(PARTITION BY benchmark_source_record_id,observation_date
      ORDER BY CASE provider WHEN 'b3_index' THEN 1 WHEN 'bcb_sgs' THEN 2 ELSE 3 END,
      captured_at DESC,capture_id DESC) rank
  FROM market.benchmark_value v
) WHERE rank=1;

CREATE OR REPLACE VIEW market.comparison_series AS
SELECT source_record_id AS series_id,symbol AS code,name,trading_date AS observation_date,
       coalesce(adjusted_close,close) AS value,
       CASE WHEN adjusted_close IS NULL THEN 'unadjusted_price' ELSE 'price' END AS unit,
       'daily' AS frequency,provider
FROM market.daily_close_series
UNION ALL
SELECT v.benchmark_source_record_id,c.abbreviation,c.name,v.observation_date,
       v.value,v.unit,v.frequency,v.provider
FROM market.benchmark_value_effective v JOIN market.benchmark_catalog c
  ON c.source_record_id=v.benchmark_source_record_id;
