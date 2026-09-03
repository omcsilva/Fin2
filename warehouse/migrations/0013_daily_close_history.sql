CREATE TABLE market.history_capture (
    capture_id VARCHAR PRIMARY KEY,
    provider VARCHAR NOT NULL CHECK(provider='brapi_v2'),
    endpoint VARCHAR NOT NULL,
    requested_symbols VARCHAR NOT NULL,
    captured_at TIMESTAMPTZ NOT NULL,
    response_sha256 VARCHAR NOT NULL,
    response_body BLOB NOT NULL,
    UNIQUE(provider,response_sha256)
);

CREATE TABLE market.daily_close (
    source_record_id VARCHAR NOT NULL,
    trading_date DATE NOT NULL,
    provider VARCHAR NOT NULL CHECK(provider='brapi_v2'),
    currency VARCHAR NOT NULL,
    close DECIMAL(28,10) NOT NULL CHECK(close>0),
    adjusted_close DECIMAL(28,10) CHECK(adjusted_close>0),
    capture_id VARCHAR NOT NULL,
    captured_at TIMESTAMPTZ NOT NULL,
    PRIMARY KEY(source_record_id,trading_date,provider)
);

CREATE VIEW market.daily_close_series AS
SELECT d.*,a.symbol,a.name
FROM market.daily_close d
JOIN market.asset_catalog a ON a.source_record_id=d.source_record_id;
