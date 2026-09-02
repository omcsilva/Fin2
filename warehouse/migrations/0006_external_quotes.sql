-- Raw response and its validated interpretation commit together, offline only.
CREATE TABLE external_quote_capture (
    capture_id VARCHAR PRIMARY KEY,
    source_record_id VARCHAR NOT NULL REFERENCES source_record(record_id),
    provider VARCHAR NOT NULL CHECK(provider='brapi_v2'),
    requested_symbol VARCHAR NOT NULL,
    endpoint VARCHAR NOT NULL,
    captured_at TIMESTAMPTZ NOT NULL,
    response_sha256 VARCHAR NOT NULL,
    response_body BLOB NOT NULL,
    status VARCHAR NOT NULL CHECK(status IN ('accepted','rejected')),
    reason VARCHAR,
    price DECIMAL(28,10),
    currency VARCHAR,
    quoted_at TIMESTAMPTZ,
    CHECK ((status='accepted' AND price>0 AND currency='BRL' AND quoted_at IS NOT NULL AND reason IS NULL)
        OR (status='rejected' AND price IS NULL AND currency IS NULL AND quoted_at IS NULL AND reason IS NOT NULL)),
    UNIQUE(source_record_id,provider,requested_symbol,response_sha256)
);
CREATE VIEW market.quote_capture AS SELECT * FROM external_quote_capture;
