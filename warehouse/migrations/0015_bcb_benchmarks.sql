CREATE VIEW market.official_benchmark_catalog AS
SELECT source_record_id,batch_id,legacy_id,name,abbreviation,DATE '2000-01-01' start_date,
 CASE abbreviation WHEN 'CDI' THEN 12 WHEN 'SLC' THEN 11 WHEN 'INF' THEN 433
  WHEN 'DOL' THEN 1 WHEN 'EUR' THEN 21619 WHEN 'IBO' THEN 7 END AS sgs_code,
 CASE abbreviation WHEN 'CDI' THEN 'percent_per_day' WHEN 'SLC' THEN 'percent_per_day'
  WHEN 'INF' THEN 'percent_per_month' WHEN 'DOL' THEN 'BRL_per_USD'
  WHEN 'EUR' THEN 'BRL_per_EUR' WHEN 'IBO' THEN 'index_points' END AS unit,
 CASE abbreviation WHEN 'INF' THEN 'monthly' ELSE 'daily' END AS frequency
FROM portfolio.reference WHERE kind='indice' AND abbreviation IN ('CDI','SLC','INF','DOL','EUR','IBO');
