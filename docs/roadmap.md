# Implementation roadmap

## Completed

- [x] Record the agreed single-user Django/DuckDB architecture.
- [x] Create package boundaries and project documentation.

## Foundation

- [x] Inspect remote Fin1 source, SQLite schemas, and document references read-only.
- [x] Create and restore a verified development snapshot of the three databases and attachments; see [backup results](fin1-backup.md).
- [ ] Review the exceptions in the [Fin1 analysis](fin1-analysis.md) using the private local snapshot.
- [ ] Coordinate a final capture without writes before cutover; the development snapshot is not an application-level freeze.
- [x] Implement a runnable read-only Django shell without auth, admin, sessions, or application SQLite.
- [x] Pin tested dependencies and document local setup commands.
- [ ] Implement DuckDB connection ownership, write locking, rollback, and resource configuration.
- [ ] Define and implement the versioned warehouse schema.
- [x] Implement the versioned DuckDB audit/ingestion schema and offline access layer.
- [x] Implement transactional snapshot ingestion, document linking, repeat-import protection, and exception reporting.
- [ ] Normalize the financial ledger and reconcile it against the preserved source records.
- [x] Add typed financial reference projections and per-application quantity checks (255 matched, 5 differences in the initial snapshot).
- [x] Add the read-only positions page with account/asset filters and source-record navigation.
- [x] Add cash reconciliation per account/currency and transaction-level running balances; retain unresolved discrepancies.
- [x] Investigate the five quantity mismatches and expose movement-level evidence without corrections.
- [x] Add indicative valuation and class allocation per original currency, with coverage and stale/missing-price warnings.
- [x] Add persistent portfolio and annual analysis selectors; reconstruct year-end quantities and annual cash flows without treating current legacy balances or prices as historical.
- [x] Add a read-only identifier inventory and snapshot price observations with provenance; see [market data](market-data.md). Provider validation and external quotes remain pending.

## First usable milestone

- [ ] Implement repeatable Fin1 import with provenance and duplicate protection.
- [ ] Preserve and migrate original imported documents and all document-to-record links.
- [ ] Add safe dashboard document viewing/download and navigation between documents and generated records.
- [x] Add read-only audit pages, document viewing/download, and navigation in both directions; visual browser verification remains pending.
- [ ] Verify file integrity, missing-file reporting, and link preservation across reimports and reversals.
- [ ] Reconcile holdings, cash, income, and valuations against Fin1.
- [ ] Build overview and allocation pages with missing-data warnings.
- [ ] Add validated manual ledger entry and corrections.
- [ ] Add generic CSV/XLSX preview, validation, and atomic commit.

## Expanded reporting and ingestion

- [ ] Add prices, FX, benchmarks, and freshness metadata.
- [x] Implement an explicit one-asset brapi v2 adapter with raw-response provenance, strict validation and a separate read-only capture panel; see [brapi](brapi.md). No valuation replacement or scheduling.
- [x] Add a user-triggered serialized background brapi update, durable progress, asynchronous completion notice, status bar, and latest accepted external-price selection. Scheduling and unsupported providers remain pending.
- [ ] Add performance, income, and cash-flow reports.
- [ ] Implement traceable cost-basis and tax estimates with verified rules.
- [ ] Add institution-specific statement adapters.
- [ ] Add API integrations and scheduling that respect database process ownership.

## Deployment and transition

- [ ] Implement and verify systemd and reverse-proxy configuration.
- [ ] Test resource use, private-network restrictions, and `/fin2/` routing.
- [ ] Verify backups and an isolated restore.
- [ ] Run alongside Fin1 through one complete update cycle.
- [ ] Resolve all reconciliation differences and obtain cutover acceptance.
