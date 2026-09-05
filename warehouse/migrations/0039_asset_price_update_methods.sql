CREATE TABLE market.asset_price_update_method (
    source_record_id VARCHAR PRIMARY KEY,
    method VARCHAR NOT NULL CHECK(method IN ('BRAPI','NENHUM')),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

INSERT INTO market.asset_price_update_method(source_record_id,method)
SELECT source_record_id,'BRAPI' FROM portfolio.asset;

CREATE TABLE market.price_update_job_asset (
    job_id VARCHAR NOT NULL,
    source_record_id VARCHAR NOT NULL,
    asset_name VARCHAR,
    symbol VARCHAR,
    method VARCHAR NOT NULL CHECK(method IN ('BRAPI','NENHUM')),
    status VARCHAR NOT NULL CHECK(status IN ('pending','already_current','accepted','rejected','failed')),
    message VARCHAR,
    queried_at TIMESTAMPTZ,
    PRIMARY KEY(job_id,source_record_id)
);

CREATE TABLE market.price_update_state (
    state_key VARCHAR PRIMARY KEY CHECK(state_key='assets'),
    last_successful_at TIMESTAMPTZ,
    job_id VARCHAR
);

INSERT INTO market.price_update_state VALUES ('assets',NULL,NULL);
