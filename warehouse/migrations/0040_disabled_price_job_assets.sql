CREATE TABLE market.price_update_job_asset_replacement (
    job_id VARCHAR NOT NULL,
    source_record_id VARCHAR NOT NULL,
    asset_name VARCHAR,
    symbol VARCHAR,
    method VARCHAR NOT NULL CHECK(method IN ('BRAPI','NENHUM')),
    status VARCHAR NOT NULL CHECK(status IN ('pending','already_current','accepted','rejected','failed','disabled')),
    message VARCHAR,
    queried_at TIMESTAMPTZ,
    PRIMARY KEY(job_id,source_record_id)
);

INSERT INTO market.price_update_job_asset_replacement
SELECT * FROM market.price_update_job_asset;
DROP TABLE market.price_update_job_asset;
ALTER TABLE market.price_update_job_asset_replacement RENAME TO price_update_job_asset;
