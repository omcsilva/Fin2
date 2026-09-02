# Scope and requirements

## Purpose

Provide one investor with a consolidated view of investments, replacing Fin1 without losing history or calculation traceability. The application is unauthenticated and restricted at the network boundary.

Single-user operation must preserve multiple financial owners and portfolios: Fin1 currently contains three holders and seven portfolios. Preserve these distinctions, application groupings, and existing HTML annotations alongside original documents. See the [Fin1 analysis](fin1-analysis.md).

## Investment coverage

- Brazilian stocks and ETFs.
- Fixed income and bank products.
- Investment funds and pensions.
- Foreign investments and currencies.

All are in the intended scope, but adapters and asset-specific calculations will be delivered incrementally.

## Ingestion

Support a repeatable Fin1 migration, manual transactions, CSV/XLSX imports, institution-specific statements or brokerage notes, and eventual API integrations. Every import needs preview, validation, duplicate detection, and provenance before committing events.

## Original documents and record navigation

Preserve Fin1's existing behavior: every imported file (statement, brokerage note, brokerage contract, or investment contract) must be retained for viewing inside the dashboard and linked to the records it generated.

- Store the original bytes, filename, document type, checksum, and import provenance outside the checkout, with metadata in DuckDB.
- From a generated record, open its source document directly; from a document, list and navigate to the records it generated.
- Support one document generating multiple records and a record referencing multiple supporting documents. Capture page/sheet/row locators when available.
- Provide an embedded viewer for supported formats and a safe in-dashboard preview plus original download for formats that cannot be embedded. Never execute uploaded active content.
- Reprocessing, corrections, and batch reversals must preserve original files and historical links.
- Migrate Fin1's stored files and existing record links, not just database values. Missing files or broken links must appear in reconciliation reports.

Document retention, viewing, and record navigation are required for the first usable migration milestone, not a later optional feature.

## Dashboard targets

| View | Required information |
| --- | --- |
| Overview | BRL valuation, invested capital, income, changes, and freshness warnings |
| Allocation | Asset class, institution, account, currency, issuer, liquidity, maturity |
| Performance | Time-weighted and money-weighted returns, benchmarks, original currency and BRL |
| Income and cash flow | Dividends, interest, amortization, benefits, maturities |
| Realized results and tax | Cost basis, gains/losses, withholding, traceable estimates and exports |
| Reconciliation | Imported versus calculated positions, missing prices/FX, duplicates, unknown assets |

Tax calculations are a review aid, not an authoritative filing. Applicable rules and effective dates must be established and verified during implementation.

## First usable milestone

Import a representative Fin1 dataset, reconcile positions and cash, and display balances and allocation in BRL. Manual entry and generic import follow before advanced performance and tax reporting.

## Constraints and open decisions

- Host: ThinkPad X230 with 8 GB total RAM; deployment: unprivileged Proxmox LXC.
- No login, admin, sessions, secondary SQLite database, or background queue.
- Preferred deployment prefix: `/fin2/`; Fin1 remains available during transition.
- Pending: Fin1 schema, source formats, market-data providers, chart library, cost-basis conventions, rounding rules, and reconciliation tolerances.
