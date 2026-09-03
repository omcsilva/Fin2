-- Reviewed provider mappings for assets that had no usable Fin1 integration.
CREATE TABLE market.asset_provider_override (
  source_record_id VARCHAR PRIMARY KEY,
  provider VARCHAR NOT NULL,
  symbol VARCHAR NOT NULL,
  multiplier DECIMAL(28,10) NOT NULL CHECK(multiplier>0),
  rationale VARCHAR NOT NULL,
  evidence JSON NOT NULL,
  decided_at TIMESTAMPTZ NOT NULL DEFAULT current_timestamp
);

CREATE VIEW market.asset_catalog_effective AS
SELECT a.* EXCLUDE(symbol,configured_provider,configured_multiplier),
  coalesce(o.symbol,a.symbol) symbol,
  coalesce(o.provider,a.configured_provider) configured_provider,
  coalesce(CAST(o.multiplier AS VARCHAR),a.configured_multiplier) configured_multiplier,
  o.rationale provider_override_rationale
FROM market.asset_catalog a
LEFT JOIN market.asset_provider_override o USING(source_record_id);
