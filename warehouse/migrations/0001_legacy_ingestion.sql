-- Audit/ingestion layer, not the final financial ledger.
CREATE TABLE import_batch (
    batch_id VARCHAR PRIMARY KEY,
    source_manifest JSON NOT NULL,
    as_of_date DATE NOT NULL,
    imported_at TIMESTAMPTZ NOT NULL DEFAULT current_timestamp
);
CREATE TABLE source_table (
    batch_id VARCHAR NOT NULL REFERENCES import_batch(batch_id),
    database_name VARCHAR NOT NULL,
    table_name VARCHAR NOT NULL,
    columns_json JSON NOT NULL,
    row_count BIGINT NOT NULL,
    PRIMARY KEY (batch_id, database_name, table_name)
);
CREATE TABLE source_record (
    record_id VARCHAR PRIMARY KEY,
    batch_id VARCHAR NOT NULL REFERENCES import_batch(batch_id),
    database_name VARCHAR NOT NULL,
    table_name VARCHAR NOT NULL,
    legacy_id BIGINT NOT NULL,
    payload JSON NOT NULL,
    UNIQUE (batch_id, database_name, table_name, legacy_id)
);
CREATE TABLE source_document (
    document_id VARCHAR PRIMARY KEY,
    batch_id VARCHAR NOT NULL REFERENCES import_batch(batch_id),
    source_path VARCHAR NOT NULL,
    original_filename VARCHAR NOT NULL,
    sha256 VARCHAR NOT NULL,
    byte_size BIGINT NOT NULL,
    storage_key VARCHAR NOT NULL,
    UNIQUE (batch_id, source_path)
);
CREATE TABLE document_record_link (
    document_id VARCHAR NOT NULL REFERENCES source_document(document_id),
    record_id VARCHAR NOT NULL REFERENCES source_record(record_id),
    relation VARCHAR NOT NULL,
    PRIMARY KEY (document_id, record_id, relation)
);
CREATE TABLE import_issue (
    issue_id VARCHAR PRIMARY KEY,
    batch_id VARCHAR NOT NULL REFERENCES import_batch(batch_id),
    code VARCHAR NOT NULL,
    record_id VARCHAR REFERENCES source_record(record_id),
    details JSON NOT NULL
);
