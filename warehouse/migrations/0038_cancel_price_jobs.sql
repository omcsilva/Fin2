CREATE TABLE price_update_job_replacement (
    job_id VARCHAR PRIMARY KEY,
    batch_id VARCHAR NOT NULL REFERENCES import_batch(batch_id),
    collection_id BIGINT,
    status VARCHAR NOT NULL CHECK(status IN ('queued','running','completed','failed','cancelled')),
    created_at TIMESTAMPTZ NOT NULL,
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ,
    target_count INTEGER NOT NULL DEFAULT 0,
    accepted_count INTEGER NOT NULL DEFAULT 0,
    rejected_count INTEGER NOT NULL DEFAULT 0,
    failed_count INTEGER NOT NULL DEFAULT 0,
    skipped_count INTEGER NOT NULL DEFAULT 0,
    message VARCHAR NOT NULL
);

INSERT INTO price_update_job_replacement SELECT * FROM price_update_job;
DROP TABLE price_update_job;
ALTER TABLE price_update_job_replacement RENAME TO price_update_job;
