-- Indicative valuation only. Never combine currencies or use future quotes.
CREATE VIEW portfolio.valuation AS
WITH classified AS (
    SELECT p.*,b.as_of_date,date_diff('day',p.price_date,b.as_of_date) AS price_age_days,
       CASE
         WHEN p.incomplete_count>0 OR p.legacy_delta IS NULL OR p.legacy_delta<>0 THEN 'quantity_review'
         WHEN p.quantity_at_cutoff<0 THEN 'negative_quantity'
         WHEN p.quantity_at_cutoff=0 THEN 'closed'
         WHEN p.currency IS NULL OR trim(p.currency)='' THEN 'missing_currency'
         WHEN p.legacy_price IS NULL OR p.legacy_price<=0 THEN 'missing_price'
         WHEN p.price_date IS NULL THEN 'missing_price_date'
         WHEN p.price_date>b.as_of_date THEN 'future_price'
         WHEN date_diff('day',p.price_date,b.as_of_date)>30 THEN 'stale_price'
         ELSE 'priced'
       END AS valuation_status
    FROM portfolio.position p JOIN import_batch b USING(batch_id)
)
SELECT *,CASE WHEN valuation_status IN ('priced','stale_price')
    THEN CAST(quantity_at_cutoff*legacy_price AS DECIMAL(38,10)) END AS reference_value
FROM classified;

CREATE VIEW portfolio.valuation_totals AS
SELECT batch_id,currency,
       count(*) FILTER(WHERE valuation_status<>'closed') AS active_count,
       count(reference_value) AS priced_count,
       count(*) FILTER(WHERE valuation_status NOT IN ('closed','priced','stale_price')) AS excluded_count,
       count(*) FILTER(WHERE valuation_status='stale_price') AS stale_count,
       sum(reference_value) AS reference_subtotal
FROM portfolio.valuation GROUP BY batch_id,currency;

CREATE VIEW portfolio.allocation AS
WITH groups AS (
    SELECT batch_id,currency,coalesce(class_name,'Sem classe') AS class_name,
           count(*) AS application_count,sum(reference_value) AS reference_value
    FROM portfolio.valuation WHERE reference_value IS NOT NULL
    GROUP BY batch_id,currency,coalesce(class_name,'Sem classe')
)
SELECT *,100.0*reference_value/nullif(sum(reference_value) OVER(PARTITION BY batch_id,currency),0) AS percentage
FROM groups;
