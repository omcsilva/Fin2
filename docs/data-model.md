# Proposed data model

Canonical projections use ISO 4217 codes (`BRL`, `USD`, and `EUR`). Legacy
labels (`REAL`, `DOL`, and `DOLAR`) remain only in the immutable imported
payload. Manual entries and new file imports are normalized before storage.

This is the proposed financial model, not an implemented financial ledger. The separate [audit/ingestion schema](legacy-import.md) is implemented. Final financial keys, precision, constraints, and transformations depend on reconciliation of Fin1 records.

The [initial Fin1 inspection](fin1-analysis.md) establishes additional requirements: preserve multiple financial owners independently of the single application user, portfolio memberships, distinct legacy applications (do not assume account/asset uniqueness), and HTML annotations. Model cash entries and investment movements as related components to prevent double counting, and distinguish expected events from settled events. Preserve legacy calculated values separately for reconciliation.

## Reference data

| Entity | Purpose |
| --- | --- |
| investor | Owner or portfolio grouping; not an authentication user |
| institution | Broker, bank, insurer, or fund platform |
| account | Brokerage, bank, pension, or foreign account |
| asset | Canonical financial instrument or product |
| asset_identifier | Ticker, ISIN, CNPJ, and institution-specific identifiers |
| asset_category | Stock, ETF, fund, fixed income, pension, cash |
| currency | Currency codes and display metadata |
| benchmark | CDI, Selic, IPCA, Ibovespa, or custom comparison series |
| tax_profile | Versioned calculation metadata, with effective dates |
| import_mapping | Source-specific normalization configuration |

## Financial and provenance data

| Entity | Purpose |
| --- | --- |
| ledger_event | Purchases, sales, contributions, withdrawals, fees, taxes, income, adjustments |
| price | Asset quotations with date, currency, and provider |
| exchange_rate | Dated rates with explicit base/quote direction and provider |
| benchmark_value | Dated benchmark observations |
| position_snapshot | External holdings/balances for reconciliation |
| fixed_income_terms | Issuer, maturity, indexer, contracted rate, principal |
| pension_plan_terms | Plan, fund, regime, and benefit metadata |
| import_batch | Checksum, source, status, timestamps, validation outcome |
| source_record | Original row/document reference and normalization lineage |
| source_document | Original file storage key, original filename, document type, media type, byte size, checksum, and ingestion timestamp |
| document_record_link | Document-to-generated/supporting-record relation, with optional page/sheet/row locator and provenance |

Document links must cover ledger events as well as other generated records, such as product terms and position snapshots. Use explicit foreign-key link tables or a constrained shared record identity; avoid unconstrained table-name/ID pairs. The final schema must support many-to-many links and preserve Fin1 identifiers for reconciliation. Associate documents with their import batches/source records so retries remain traceable without duplicating financial events.

Store file bytes outside DuckDB and outside the checkout. Use stable managed storage keys rather than original filenames as paths. Preserve original bytes; previews are derived artifacts. Because filesystem writes and database commits are not one transaction, stage and verify files before publishing document links, and define recovery for interrupted imports. Do not delete original documents when reversing a committed batch.

Use `ledger_event` as the proposed canonical name instead of `transaction`. Income and cash-flow reporting should derive from the ledger; if a separate cash-flow table is introduced, define its relationship explicitly to prevent double counting.

## Invariants

- Use Python Decimal and DuckDB DECIMAL for money, quantities, rates, and cost-basis arithmetic; choose precision from real source examples.
- Preserve original currency and values. Conversions need a dated rate and provenance.
- Distinguish trade date, settlement date, and cash-event date.
- Preserve source account, institution, description, import batch, and source record identifiers.
- Define stable duplicate keys without treating every identical-looking legitimate trade as a duplicate.
- Represent corrections and committed batch reversals as linked events; preserve originals.
- Validate event types, signs, required fields, and referential integrity before commit.
- Missing market data must be visible, never silently valued as zero.
- Specify valuation cutoffs, FX direction, rounding, corporate actions, and cost basis before implementing reports.

## Migration policy

Version SQL in `warehouse/migrations/`. The future runner should record applied versions and checksums, reject changed applied migrations, and commit each supported migration atomically. Back up before schema changes. A schema reference may be generated later; do not maintain competing handwritten schema sources.
