CREATE TABLE market.asset_symbol_alias (
  provider_symbol VARCHAR NOT NULL,
  canonical_symbol VARCHAR NOT NULL,
  valid_from DATE NOT NULL,
  valid_to DATE NOT NULL,
  source VARCHAR NOT NULL,
  PRIMARY KEY(provider_symbol,canonical_symbol)
);

INSERT INTO market.asset_symbol_alias VALUES
  ('BVMF3','B3SA3',DATE '2008-08-20',DATE '2018-03-25','ticker change'),
  ('KROT3','COGN3',DATE '2007-07-23',DATE '2019-10-10','ticker change'),
  ('VVAR3','VIIA3',DATE '2010-12-13',DATE '2021-08-15','ticker change');
