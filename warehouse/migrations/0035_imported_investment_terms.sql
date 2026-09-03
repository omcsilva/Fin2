CREATE TABLE ledger.file_import_investment_term (
  event_id VARCHAR PRIMARY KEY,
  product_name VARCHAR NOT NULL,
  unit_price DECIMAL(28,10),
  yield_text VARCHAR,
  maturity_year INTEGER,
  institution VARCHAR,
  protocol VARCHAR
);
