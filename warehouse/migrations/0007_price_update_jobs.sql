CREATE TABLE price_update_job (
    job_id VARCHAR PRIMARY KEY,
    batch_id VARCHAR NOT NULL REFERENCES import_batch(batch_id),
    collection_id BIGINT,
    status VARCHAR NOT NULL CHECK(status IN ('queued','running','completed','failed')),
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

CREATE VIEW market.latest_external_price AS
SELECT * EXCLUDE(row_number) FROM (
  SELECT source_record_id,price,currency,quoted_at,captured_at,capture_id,
    row_number() OVER(PARTITION BY source_record_id ORDER BY quoted_at DESC,captured_at DESC,capture_id DESC) row_number
  FROM external_quote_capture WHERE status='accepted'
) WHERE row_number=1;
