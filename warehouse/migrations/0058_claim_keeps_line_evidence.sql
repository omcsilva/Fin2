-- The review staging (xp_statement, xp_statement_line, xp_statement_decision) is
-- discarded when the load is concluded, but two integrity checks in _validate
-- must survive it: the overlap check compares the description and settlement
-- date of already confirmed lines, and the link check compares fingerprints.
-- The claim already kept the fingerprint, so it now carries the other two fields
-- and existing claims are backfilled from the lines still present.
ALTER TABLE ledger.xp_statement_claim ADD COLUMN description VARCHAR;
ALTER TABLE ledger.xp_statement_claim ADD COLUMN settlement_date VARCHAR;

UPDATE ledger.xp_statement_claim c
   SET description = json_extract_string(r.raw, '$.description'),
       settlement_date = json_extract_string(r.raw, '$.settlement_date')
  FROM ledger.xp_statement_line r
 WHERE r.import_id = c.import_id AND r.line_number = c.line_number;
