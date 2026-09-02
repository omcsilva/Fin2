# Fin2

Fin2 is a planned single-user investment dashboard built with Django and DuckDB. It will replace Fin1, the existing Django/SQLite dashboard, after a side-by-side migration and reconciliation.

Fin2 has no application login. Access must be restricted to a trusted LAN or VPN through firewall or reverse-proxy rules.

## Status

The repository contains offline DuckDB ingestion, a repeatable Fin1 snapshot importer, document storage/linking, exception reporting, and a runnable read-only Django dashboard. Browse legacy records, documents, and review flags at `/fin2/`. The normalized financial ledger and investment calculations remain pending. All real financial data and original documents remain outside this repository.

## Architecture decisions

- Django templates with HTMX for partial updates; chart library remains undecided.
- One persistent DuckDB database for reference data, financial events, and import metadata, accessed through the official Python client.
- No secondary SQLite database, Django ORM portfolio models, authentication, admin, or sessions.
- CSRF protection remains enabled for modifying web requests.
- One Gunicorn worker in an unprivileged Proxmox LXC on an 8 GB ThinkPad X230.
- No Celery, Redis, or separate database server.
- Financial data, source documents, and secrets remain outside the repository.
- Preserve Fin1's original imported files for dashboard viewing, with navigation between each document and the records it generated.

## Repository structure

```text
config/                 Django settings, routing, and WSGI (implementation pending)
fin2/
  dashboard/            Pages, filters, and presentation
  portfolio/            Assets, institutions, accounts, and product terms
  transactions/         Ledger events and manual entry
  imports/              Preview, validation, adapters, and provenance
  market_data/          Prices, FX, and benchmarks
  analytics/            Positions, allocation, performance, and cash flow
  tax/                  Traceable realized results and tax estimates
warehouse/
  migrations/           Versioned DuckDB SQL migrations
  repositories/         Parameterized database access
  queries/              Analytical SQL
templates/              Django templates
static/                 CSS, JavaScript, and images
tests/                  Synthetic fixtures and tests
deploy/                 Future service and proxy configuration
docs/                   Design and operations documentation
```

`manage.py`, runtime configuration, dependency metadata, and SQL schema will be added when implementing the runnable scaffold. Python package markers reserve the module paths without implementing behavior.

## Documentation

- [Scope and requirements](docs/requirements.md)
- [Architecture and concurrency](docs/architecture.md)
- [Proposed data model](docs/data-model.md)
- [Fin1 migration and reconciliation](docs/fin1-migration.md)
- [Initial Fin1 analysis](docs/fin1-analysis.md)
- [Verified Fin1 development snapshot](docs/fin1-backup.md)
- [DuckDB ingestion and local commands](docs/legacy-import.md)
- [Run the Django dashboard](docs/dashboard.md)
- [Financial reference data and quantity checks](docs/positions.md)
- [Cash reconciliation and quantity investigation](docs/cash-reconciliation.md)
- [Reference valuation and allocation](docs/valuation.md)
- [Deployment and security](docs/deployment.md)
- [Development conventions](docs/development.md)
- [Implementation roadmap](docs/roadmap.md)

The next step is to review ingestion exceptions and define the normalized financial model. A coordinated final source capture remains required before cutover.
