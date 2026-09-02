# Development conventions

## Scaffold status

The offline DuckDB ingestion layer and read-only Django dashboard are implemented; see [ingestion commands](legacy-import.md) and [dashboard setup](dashboard.md). Do not run Django ORM migrations or create an application SQLite database. SQLite files are used only as legacy inputs and synthetic test fixtures.

`requirements.txt` pins the tested dependencies. `manage.py`, settings, routing, and WSGI are present. Packaging metadata and production deployment remain pending.

## Boundaries

- HTTP views call services; services use repositories for persistence.
- Keep SQL parameterized and in the warehouse layer. Never interpolate user input into SQL.
- Keep financial arithmetic out of templates and provider adapters.
- Adapters normalize source data into a shared draft format; validation precedes commit.
- Warehouse schema migrations are separate from Django ORM migrations.
- Do not introduce auth, admin, sessions, SQLite, Celery, or Redis without revisiting the recorded architecture.

## Data handling

Use synthetic fixtures in the repository. Keep real statements, exports, database files, API keys, and personal identifiers outside it. Review new files for private data even when `.gitignore` is present; generic CSV/XLSX/PDF files are not globally ignored so synthetic fixtures and public documentation remain possible.

## Verification as features arrive

- Django checks and request smoke tests for the application shell.
- Mutation/CSRF tests without auth or sessions.
- Repository transaction rollback, migration checksums, and write serialization tests.
- Import duplicate detection, preview/commit parity, failure rollback, and reversal tests.
- Decimal arithmetic, currency conversion, corporate actions, and reconciliation fixtures.
- Prefix routing and static assets under `/fin2/`.
- Backup restore and a resource smoke test in the intended LXC.

Add tests for implemented behavior rather than assertions about empty directories. Document commands and observed results as the runnable application becomes available.
