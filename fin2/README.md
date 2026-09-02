# Application packages

| Package | Responsibility |
| --- | --- |
| dashboard | Views, filters, and display of service results |
| portfolio | Master data, asset identifiers, accounts, and product terms |
| transactions | Canonical ledger validation, manual entry, and adjustments |
| imports | Fin1/file adapters, preview, validation, deduplication, and batch lifecycle |
| market_data | Price, currency, and benchmark provider normalization |
| analytics | Holdings, allocation, returns, income, and reconciliation |
| tax | Cost basis, realized results, and versioned calculation rules |

`imports/fin1.py` implements offline ingestion; `imports/report.py` exports private exceptions. `portfolio/prepare.py` validates typed financial projections and exports quantity discrepancies. `dashboard/views.py` provides read-only pages, including positions. The editable ledger and other calculation packages remain pending. See [positions](../docs/positions.md), [ingestion commands](../docs/legacy-import.md), and [dashboard instructions](../docs/dashboard.md).
