CREATE TABLE market.asset_price_query_success (
    source_record_id VARCHAR NOT NULL,
    provider VARCHAR NOT NULL CHECK(provider='brapi_v2'),
    queried_at TIMESTAMPTZ NOT NULL,
    quoted_at TIMESTAMPTZ NOT NULL,
    price DECIMAL(28,10) NOT NULL CHECK(price>0),
    currency VARCHAR NOT NULL CHECK(currency='BRL'),
    capture_id VARCHAR NOT NULL,
    PRIMARY KEY(source_record_id,queried_at)
);

INSERT INTO market.asset_price_query_success
SELECT source_record_id,provider,captured_at,quoted_at,price,currency,capture_id
FROM external_quote_capture WHERE status='accepted';

CREATE OR REPLACE VIEW market.latest_external_price AS
SELECT * EXCLUDE(row_number) FROM (
  SELECT source_record_id,price,currency,quoted_at,queried_at AS captured_at,capture_id,
    row_number() OVER(PARTITION BY source_record_id ORDER BY queried_at DESC,capture_id DESC) row_number
  FROM market.asset_price_query_success
) WHERE row_number=1;
