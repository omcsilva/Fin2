-- Status belongs to the editable catalog. Imported evidence remains immutable.
-- Existing catalogs without status expose an empty default, never an inferred one.
CREATE OR REPLACE VIEW catalog.effective_record AS
WITH effective AS (
 SELECT s.batch_id,s.record_id,s.database_name,s.table_name,s.legacy_id,
        coalesce(c.payload,s.payload) payload
 FROM source_record s LEFT JOIN catalog.record c ON c.record_id=s.record_id
 UNION ALL
 SELECT c.batch_id,c.record_id,'db.sqlite3',c.table_name,c.legacy_id,c.payload
 FROM catalog.record c WHERE NOT EXISTS(SELECT 1 FROM source_record s WHERE s.record_id=c.record_id)
)
SELECT * EXCLUDE(payload),
  CASE WHEN table_name IN ('fin1_titular','fin1_instituicao','fin1_produto','fin1_ativo')
    THEN json_merge_patch(payload,json_object('status',coalesce(json_extract_string(payload,'$.status'),'')))
    ELSE payload END payload
FROM effective;
