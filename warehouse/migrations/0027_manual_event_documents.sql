-- Documents attached to new canonical events. Source documents remain immutable.
CREATE TABLE ledger.manual_event_document (
  event_id VARCHAR NOT NULL,
  document_id VARCHAR NOT NULL,
  relation VARCHAR NOT NULL DEFAULT 'supporting_document',
  linked_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY(event_id,document_id,relation)
);
