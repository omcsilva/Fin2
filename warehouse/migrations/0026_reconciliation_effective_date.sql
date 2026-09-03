-- Date from which a reviewed quantity override is valid in historical reports.
ALTER TABLE ledger.reconciliation_decision ADD COLUMN effective_date DATE;
