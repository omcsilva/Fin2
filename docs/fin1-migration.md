# Fin1 migration and reconciliation

## Current status

Fin1 uses Django and SQLite. Its remote source tree, three SQLite files, and
attachment archive were inspected read-only on 2026-08-31. Fin1 is now frozen
in read-only mode, and a [verified final capture](fin1-backup.md) made on
2026-09-02 is byte-for-byte identical in financial content to the development
capture. Its 5,654 records, 298 documents and 729 links are the final imported
audit lot. Future incremental synchronization and extra reimport-link machinery
are outside scope. Existing provenance and document links remain part of the
audit trail and must not be discarded.

The private final reconciliation report confirms 260 applications, 2,379
movements and 2,428 cash entries. All five quantity discrepancies now have
audited canonical decisions. “Reais em espécie” was a manual earmarked-cash
control whose latest movement explicitly closed both `em_carteira` and
`financeiro`; its stale application quantity was therefore overridden to zero
without changing the imported record. Cash decisions are complete. The APEX
Marcos (Banco Inter) history was completed with the two withdrawals of
16 April 2024 reported by the user; the canonical balance is zero and the
declaration remains recorded as its evidence.

The XP Bancos FIC FIRF CP application is also canonically closed. Its imported
25 February 2025 redemption and matching withholding-tax entry explicitly set
the legacy running position and financial amount to zero, although the source
omitted the redeemed quantity and left the application aggregate unchanged.

## Inputs needed

- Fin1 source tree, including models and calculation/import code, without credentials.
- Consistent read-only SQLite backup, kept outside the checkout.
- Representative statements and exports, handled as private financial data.
- The full stored-document archive (statements, brokerage notes, brokerage/investment contracts) and the Fin1 relationships linking each file to its generated records.
- Known reporting dates and corresponding holdings, cash, income, and valuation totals.

## Procedure

1. Preserve Fin1 and take a consistent backup; work only on copies.
2. Inventory tables, relationships, date/currency conventions, and calculations.
3. Record source-to-target mappings and unresolved cases before import.
4. Import reference data, then events, quotations, and reconciliation snapshots.
5. Track each batch and source record. Rerunning an identical batch must not create duplicates.
6. Compare holdings and cash by account/asset/currency at agreed cutoffs.
7. Compare invested capital, income, realized results, and valuation using identical price and FX inputs.
8. Record each difference, cause, and resolution; distinguish migrated-data defects from intentional calculation changes.
9. After reconciliation, make Fin1 read-only and run Fin2 through a complete update cycle.
10. Retire Fin1 only after explicit cutover acceptance; retain rollback material.

## Acceptance evidence

Migrate original documents alongside their metadata and record links. Compare file counts, byte sizes, and checksums; verify that every migrated relationship resolves to the intended document and record. Report missing source files explicitly rather than silently dropping links. Verify dashboard viewing and navigation in both directions for representative formats, including a document that generated multiple records. Preserve original files and provenance across repeat imports and batch reversals.

Keep a reconciliation report outside the repository containing source identifiers, reporting cutoff, mapping version, row counts, totals, differences, and agreed tolerances. Do not invent a blanket monetary tolerance before reviewing rounding and source precision.

## Rollback

Retain the original Fin1 database and configuration. Do not modify Fin1 during import development. Before cutover, define how transactions entered only in Fin2 will be exported or replayed if reverting. Restoring an older database without accounting for new events is not a complete rollback.
