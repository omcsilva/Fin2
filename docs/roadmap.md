# Implementation roadmap

## Completed

- [x] Record the agreed single-user Django/DuckDB architecture.
- [x] Create package boundaries and project documentation.

## Foundation

- [x] Inspect remote Fin1 source, SQLite schemas, and document references read-only.
- [x] Create and restore a verified development snapshot of the three databases and attachments; see [backup results](fin1-backup.md).
- [ ] Review the exceptions in the [Fin1 analysis](fin1-analysis.md) using the private local snapshot.
- [x] Capture and verify the final frozen Fin1 source; its financial content is identical to the initial snapshot.
- [x] Implement a runnable read-only Django shell without auth, admin, sessions, or application SQLite.
- [x] Pin tested dependencies and document local setup commands.
- [x] Implement DuckDB connection ownership, serialized write locking, rollback, and resource configuration.
- [x] Define and implement the versioned warehouse schema through the initial writable ledger.
- [x] Implement the versioned DuckDB audit/ingestion schema and offline access layer.
- [x] Implement transactional snapshot ingestion, document linking, repeat-import protection, and exception reporting.
- [ ] Complete normalization of the financial ledger and reconcile it against the preserved source records; all position differences are resolved, and APEX is the sole pending cash decision because its preserved statements end in February 2024.
- [x] Add typed financial reference projections and per-application quantity checks (255 matched, 5 differences in the initial snapshot).
- [x] Add the read-only positions page with account/asset filters and source-record navigation.
- [x] Add cash reconciliation per account/currency and transaction-level running balances; retain unresolved discrepancies.
- [x] Investigate and resolve the five quantity mismatches through audited overrides while preserving the original records.
- [x] Add indicative valuation and class allocation per original currency, with coverage and stale/missing-price warnings.
- [x] Add persistent portfolio and annual analysis selectors; reconstruct year-end quantities and annual cash flows without treating current legacy balances or prices as historical.
- [x] Add a read-only identifier inventory and snapshot price observations with provenance; see [market data](market-data.md). Provider validation and external quotes remain pending.

## First usable milestone

- [x] Implement repeatable Fin1 import with provenance and duplicate protection; final frozen capture reused the existing content-addressed lot.
- [x] Preserve and migrate original imported documents and all document-to-record links.
- [x] Add safe dashboard document viewing/download and navigation between documents and generated records.
- [x] Add read-only audit pages, document viewing/download, and navigation in both directions; visual browser verification remains pending.
- [x] Verify file integrity and link preservation against the final frozen capture. Future incremental reimports and batch reversal machinery are outside scope.
- [ ] Reconcile holdings, cash, income, and valuations against Fin1.
- [x] Add a consolidated reconciliation dashboard with direct links to canonical cash/position evidence and preserved documents.
- [x] Build overview and allocation pages with per-currency totals and missing-data warnings.
- [x] Add validated manual ledger entry and corrections through compensating reversals.
- [x] Add generic CSV/XLSX preview, full-file validation, original-file preservation, event links, and atomic commit.

## Expanded reporting and ingestion

- [x] Add audited catalog screens for owners, institutions, currencies, portfolios,
  accounts, assets, applications and portfolio membership, preserving imported records.
  Asset identifiers and fixed-income descriptive terms are editable; changing existing
  structural relationships and physical deletion remain intentionally unavailable.

- [x] Add FX, official benchmarks, freshness metadata, and a base-100 historical comparison view. Ibovespa coverage after the discontinued SGS series still awaits B3 files.
- [x] Implement an explicit one-asset brapi v2 adapter with raw-response provenance, strict validation and a separate read-only capture panel; see [brapi](brapi.md). No valuation replacement or scheduling.
- [x] Add a user-triggered serialized background brapi update, durable progress, asynchronous completion notice, status bar, and latest accepted external-price selection. Scheduling and unsupported providers remain pending.
- [x] Add performance, income, and cash-flow reports, including market variation, official references and per-application since-inception XIRR when the terminal valuation and dated flows are complete.
- [x] Classify imported cash flows with traceable source-link and description rules; identify same-date/value/currency internal-transfer pairs and retain unmatched rows as explicit exceptions.
- [ ] Implement traceable cost-basis and tax estimates with verified rules. Moving-average cost, exact fee allocation, monthly exemptions, loss carryforwards and candidate IRRF deductions are available; IRRF competence and day-trade review remain pending.
- [ ] Add institution-specific statement adapters. The common adapter contract,
  confidence-based detection, parser provenance and row/sheet locators are complete;
  Clear/XP brokerage notes and Apex USD statement movements are supported. Apex
  opening/closing balances are stored as reconciliation evidence; the remaining
  institutions are pending.
- [ ] Add API integrations and scheduling that respect database process ownership.

## Deployment and transition

- [x] Implement and verify systemd and reverse-proxy configuration on t1django.lan.
- [ ] Test resource use, private-network restrictions, and `/fin2/` routing.
- [x] Verify local production backup and an isolated restore, including documents and catalog images.
- [ ] Define backup retention and encrypted off-container copies; enable HTTPS.
- [ ] Run alongside Fin1 through one complete update cycle.
- [ ] Resolve all reconciliation differences and obtain cutover acceptance.
