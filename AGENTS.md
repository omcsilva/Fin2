# AGENTS.md

## 1. Prime Directive

Existing code is not automatically the desired architecture.

Previous human or AI-assisted iterations may have introduced:

- accidental complexity;
- duplicated logic;
- abandoned implementations;
- obsolete compatibility layers;
- unnecessary abstractions;
- redundant tests;
- weak assertions;
- excessive mocking;
- unused dependencies.

Preserve required behavior, not accidental implementation structure.

The agent must optimize for:

1. correctness;
2. simplicity;
3. maintainability;
4. testability;
5. security;
6. observability;
7. minimal change surface;
8. preservation of externally observable behavior.

The objective is NOT to maximize generated code.

Prefer deleting unnecessary code over adding new abstractions.

---

# 2. Project Context

This is a Python application built with Django.

## Runtime

- Python version: `[fill in, for example 3.12]`
- Django version: `[fill in]`
- Dependency manager: `[uv | Poetry | pip-tools | pip]`
- Database: `[PostgreSQL | SQLite | MySQL | Oracle | other]`
- Cache: `[Redis | Memcached | none | other]`
- Task queue: `[Celery | Django-Q | RQ | none | other]`
- Web interface: `[WSGI | ASGI]`
- Test framework: `[pytest + pytest-django | Django test runner]`
- Static type checker: `[mypy + django-stubs | pyright | none]`
- Linter and formatter: `[Ruff | other]`
- Application server: `[Gunicorn | Uvicorn | Daphne | other]`

Do not change these choices without an explicit task or a clearly
documented technical necessity.

Do not infer versions from memory. Inspect:

- `pyproject.toml`;
- `requirements*.txt`;
- `uv.lock`;
- `poetry.lock`;
- `Pipfile.lock`;
- Docker files;
- CI configuration.

The lock file and CI configuration are authoritative when documentation
and actual configuration disagree.

---

# 3. Repository Map

Update this section to match the repository.

Typical structure:

    manage.py
    pyproject.toml
    config/
        settings/
            base.py
            local.py
            test.py
            production.py
        urls.py
        asgi.py
        wsgi.py
    apps/
        <django_app>/
            admin.py
            apps.py
            forms.py
            managers.py
            migrations/
            models.py
            selectors.py
            services.py
            tasks.py
            urls.py
            views.py
            tests/
    templates/
    static/
    tests/
    scripts/

Actual project structure:

- `[path]`: `[responsibility]`
- `[path]`: `[responsibility]`
- `[path]`: `[responsibility]`

Before modifying code, locate the real settings module, installed apps,
URL configuration, test configuration and architectural conventions.

Do not create directories such as `services/`, `repositories/`,
`selectors/` or `use_cases/` merely because they are common patterns.

Use them only if the repository already follows that convention or if
they solve a demonstrated design problem.

---

# 4. Architecture and Dependency Boundaries

## 4.1 General direction

Prefer a modular Django monolith unless the repository explicitly uses
another architecture.

Within each Django app, preserve the following separation when already
established:

    HTTP layer
        views, serializers, forms
            |
            v
    application/business layer
        services, use cases
            |
            v
    domain/data access layer
        models, managers, QuerySets, selectors

External integrations should be isolated behind narrow interfaces where
doing so improves testability or prevents vendor-specific behavior from
spreading through the application.

Do not introduce a repository layer that merely duplicates the Django
ORM without adding a meaningful boundary.

Do not move all business logic into models by default.

Do not move all business logic into services by default.

Place logic according to responsibility:

- model invariants and model-local behavior may belong in models;
- reusable query behavior may belong in custom QuerySets or managers;
- orchestration across models or systems may belong in services;
- HTTP parsing and response formatting belong in views, forms or
  serializers;
- presentation logic belongs in templates or presentation helpers;
- background execution concerns belong in task modules;
- framework-independent calculations should remain framework-independent
  when practical.

## 4.2 Public contracts

Treat the following as potentially public contracts:

- URL names and paths;
- HTTP status codes;
- response payloads;
- template context keys;
- form fields and validation messages;
- serializer fields;
- model fields;
- database constraints;
- signals;
- management command interfaces;
- Celery task names and signatures;
- settings consumed outside the app;
- import paths used by other modules;
- admin actions;
- API schemas;
- emitted events.

Do not change them during refactoring without explicit authorization.

---

# 5. Standard Commands

Prefer repository-defined commands over raw tool invocations.

Authoritative entry points, in order of preference:

1. `Makefile`;
2. `justfile`;
3. task runner configuration;
4. `pyproject.toml` scripts;
5. project documentation;
6. direct commands.

Fill in or adapt these commands for the repository.

## Environment setup

    [uv sync | poetry install | python -m pip install -r requirements.txt]

## Django system check

    python manage.py check

## Check migrations

    python manage.py makemigrations --check --dry-run

## Unit and integration tests

Preferred when pytest is configured:

    pytest

Alternative when the Django test runner is configured:

    python manage.py test

## Formatting validation

    ruff format --check .

## Formatting application

    ruff format .

## Lint validation

    ruff check .

## Safe lint fixes

    ruff check --fix .

## Static type checking

    mypy .

## Coverage

    pytest --cov --cov-report=term-missing

## Deployment configuration check

    python manage.py check --deploy

The deployment check must use the appropriate production settings:

    DJANGO_SETTINGS_MODULE=config.settings.production \
        python manage.py check --deploy

## Security and dependency analysis

    [pip-audit | safety | configured project command]

## Mutation testing

    [mutmut run | configured project command]

## Build or packaging validation

    [configured project command]

Never claim that a command passed unless it was actually executed.

Never replace a project command with another tool merely because the
agent prefers that tool.

---

# 6. Verification Gates

The repository should expose two deterministic verification gates.

## 6.1 Fast gate

Preferred command:

    make check-fast

Equivalent logical checks:

1. formatting validation;
2. lint;
3. Django system check;
4. migration drift check;
5. static type checking, if configured;
6. affected or fast unit tests.

Example implementation:

    ruff format --check .
    ruff check .
    python manage.py check
    python manage.py makemigrations --check --dry-run
    mypy .
    pytest -m "not slow" -q

Do not add `mypy` or test markers to the command unless they are
configured and functional in the repository.

## 6.2 Full gate

Preferred command:

    make check-all

Equivalent logical checks:

1. all checks from `check-fast`;
2. complete test suite;
3. integration tests;
4. coverage thresholds;
5. build validation;
6. security checks;
7. production deployment check;
8. mutation tests, if configured and economically appropriate.

Example implementation:

    make check-fast
    pytest
    python manage.py check --deploy
    pip-audit

Use the real production settings for `check --deploy`.

Do not use development secrets as a substitute for production secrets
in CI unless they are explicitly non-production placeholder values.

---

# 7. Operating Modes

Before editing, classify the task internally as one primary mode:

1. `FEATURE`
2. `BUGFIX`
3. `MIGRATION`
4. `REFACTOR`
5. `STABILIZATION`
6. `REVIEW`

A task may require secondary activities, but one mode must remain
primary.

Do not silently transform:

- a bug fix into a broad rewrite;
- a feature into a dependency upgrade;
- a refactoring into an API redesign;
- test cleanup into removal of behavioral coverage.

---

# 8. Required Initial Inspection

Before modifying code:

1. inspect `git status`;
2. inspect relevant application modules;
3. inspect nearby tests;
4. inspect `pyproject.toml` and test configuration;
5. inspect Django settings relevant to the task;
6. inspect URLs, models, forms, serializers and migrations when affected;
7. identify public contracts;
8. determine the verification commands;
9. run an appropriate baseline.

Do not overwrite unrelated uncommitted user changes.

Do not revert changes that were present before the agent started.

Record pre-existing failures separately from failures introduced by the
current task.

If the complete suite is impractical during initial inspection, run the
smallest relevant test scope first, then run the complete applicable
gate before declaring completion.

---

# 9. FEATURE Mode

Use this mode for new behavior.

Process:

1. identify acceptance criteria;
2. identify affected Django apps;
3. inspect existing models, views, forms, serializers and services;
4. identify public contracts;
5. write or update behavioral tests;
6. implement the smallest correct change;
7. run focused tests;
8. run `check-fast`;
9. inspect migrations;
10. run `check-all` when the change is ready for integration;
11. inspect the final diff.

Do not perform unrelated repository-wide cleanup.

If existing structure blocks a safe implementation, perform only the
minimum preparatory refactoring required.

Report broader cleanup separately.

---

# 10. BUGFIX Mode

Use this mode when actual behavior differs from expected behavior.

Process:

1. state the observed behavior;
2. state the expected behavior;
3. reproduce the defect;
4. identify the root cause;
5. add or identify a regression test;
6. implement the smallest safe correction;
7. run the regression test;
8. run related application tests;
9. run the applicable verification gates.

Do not modify a valid test merely to make it pass.

Before changing a failing test, determine whether:

- production code is incorrect;
- the test expectation is obsolete;
- the requirement changed;
- fixture data is wrong;
- settings differ between environments;
- transaction isolation is missing;
- test order dependence exists;
- time, locale or timezone assumptions are wrong;
- external services are being called unintentionally.

A passing suite is not sufficient if valid assertions were weakened.

---

# 11. MIGRATION Mode

Use this mode for model or database schema changes.

## Before creating a migration

1. inspect existing migrations;
2. inspect database constraints and indexes;
3. inspect all uses of the affected field or model;
4. consider existing production data;
5. determine whether the operation is backward-compatible;
6. determine whether application deployment and schema deployment must
   be separated.

## Rules

Never edit an already-applied migration solely to make current code
cleaner.

Prefer a new migration unless project policy explicitly permits
squashing or editing unapplied migrations.

Never create an empty or unrelated migration.

Run:

    python manage.py makemigrations --check --dry-run
    python manage.py migrate --plan

When a migration is intentionally created, inspect the generated file.
Do not trust generated migrations without review.

For data migrations:

- use historical models from `apps.get_model`;
- avoid importing current model classes;
- make operations deterministic;
- consider reverse operations;
- avoid loading an unbounded table into memory;
- use batching when data volume may be large;
- document non-reversible migrations;
- avoid calling model methods that may change over time.

Consider locking, table rewrites and deployment compatibility for large
or critical tables.

Schema changes in critical environments require human review and a
rollback or forward-recovery strategy.

---

# 12. REFACTOR Mode

Use this mode when changing internal structure without intentionally
changing behavior.

## Look for

- duplicated business rules;
- dead code;
- unused imports;
- unused model methods;
- unnecessary wrappers;
- large views;
- fat forms or serializers with mixed responsibilities;
- QuerySets evaluated repeatedly;
- hidden database access;
- excessive signals;
- unnecessary signal receivers;
- duplicated validation;
- broad exception handling;
- circular imports;
- service functions with unclear boundaries;
- obsolete compatibility branches;
- stale feature flags;
- multiple implementations of the same workflow;
- tests coupled to private methods.

## Rules

Do not add new functionality.

Do not intentionally change public contracts.

Prefer small behavior-preserving transformations.

Run focused tests after each meaningful transformation.

Prefer:

    direct and explicit code

over:

    generic framework built for hypothetical reuse

Do not introduce:

- dependency injection containers;
- repository abstractions over ordinary ORM usage;
- event buses;
- command buses;
- generic base classes;
- custom metaprogramming;

unless the repository already uses them or the task clearly requires
them.

---

# 13. STABILIZATION Mode

Use this mode after several feature/revision cycles.

The objective is:

    preserve required behavior while reducing accidental complexity.

## Phase 1: Establish baseline

Before editing:

1. inspect `git status` and the current diff;
2. run relevant tests;
3. run `python manage.py check`;
4. run formatting and lint validation;
5. run the migration drift check;
6. record pre-existing failures.

## Phase 2: Inspect Django-specific debt

Search for:

- duplicate views or endpoints;
- obsolete URL routes;
- unused forms or serializers;
- duplicate model validations;
- business logic duplicated between forms, serializers and models;
- model methods without consumers;
- unused custom managers or QuerySets;
- unnecessary signals;
- signals whose side effects are not tested;
- `save()` overrides with surprising behavior;
- repeated queries inside loops;
- accidental N+1 query patterns;
- repeated template queries;
- stale migrations generated during abandoned iterations;
- unused settings;
- duplicate test factories and fixtures;
- excessive `mock.patch`;
- tests that mock the Django ORM without a concrete need;
- redundant tests of framework behavior;
- broad `except Exception`;
- `mark_safe`, `safe` or disabled auto-escaping;
- disabled CSRF protection;
- hardcoded secrets;
- debugging code;
- `print()` statements;
- unused dependencies;
- temporary feature flags;
- commented-out implementations.

Treat these as findings to investigate, not automatic deletion targets.

## Phase 3: Plan internally

Order work by:

1. low-risk dead code removal;
2. import and dependency cleanup;
3. duplicated test setup;
4. duplicated business logic;
5. naming and readability;
6. query optimization supported by evidence;
7. responsibility separation;
8. architectural change.

Avoid combining multiple high-risk changes.

## Phase 4: Refactor incrementally

For each coherent change:

1. make one small transformation;
2. run focused tests;
3. inspect SQL behavior when query logic changed;
4. inspect migration state when models changed;
5. continue only from a known-good state.

## Phase 5: Independent review

After stabilization, switch mentally to `REVIEW` mode.

Do not defend an implementation merely because the same agent created
it.

Review the entire diff from first principles.

---

# 14. Django Model Rules

## 14.1 Models

Models should express persistent data, constraints and behavior closely
associated with that data.

Avoid turning models into unbounded orchestration objects.

For model changes, inspect:

- field defaults;
- `null` versus `blank`;
- uniqueness;
- database constraints;
- indexes;
- `on_delete`;
- timezone behavior;
- validation;
- migration compatibility;
- serialization effects.

Do not override `save()` for cross-system workflows or uncontrolled
side effects.

If `save()` or `delete()` is overridden:

- preserve the method signature;
- forward relevant arguments;
- test normal and edge behavior;
- consider bulk operations, which may bypass model methods.

Prefer database constraints for invariants that must remain valid under
concurrency.

Do not assume `Model.full_clean()` is automatically called by
`Model.save()`.

## 14.2 QuerySets and managers

Use custom QuerySets or managers for reusable query composition.

Avoid managers that hide writes, network calls or unrelated side
effects.

Preserve lazy QuerySet evaluation.

Do not accidentally convert a lazy QuerySet into a list unless required.

Use `select_related()` and `prefetch_related()` only for demonstrated
access patterns.

Do not add query optimization without a test, query-count assertion,
profiling evidence or a clear repeated-access pattern.

## 14.3 Transactions

Use `transaction.atomic()` for operations that must commit or fail as a
unit.

Keep transaction boundaries as short as practical.

Avoid external network calls while holding a database transaction.

For side effects that must occur only after a successful commit,
consider `transaction.on_commit()`.

Do not claim a concurrency issue is fixed solely because a transaction
was added. Evaluate locking, isolation, uniqueness and retry behavior.

---

# 15. Views, Forms, Serializers and Templates

## Views

Views should coordinate HTTP concerns:

- authentication;
- authorization;
- input extraction;
- service invocation;
- response construction.

Avoid embedding large business workflows directly in views.

Preserve:

- status codes;
- redirects;
- headers;
- content types;
- pagination;
- URL names;
- error response structure.

## Forms and serializers

Use forms or serializers for input validation appropriate to their
interface.

Do not duplicate the same business invariant independently across
several interfaces without a shared authoritative rule.

Never trust client-supplied ownership, role or authorization data.

Validation does not replace authorization.

## Templates

Preserve Django auto-escaping.

Treat uses of the following as security-sensitive:

- `mark_safe`;
- the `safe` template filter;
- disabled `autoescape`;
- handcrafted HTML from untrusted data.

Do not perform expensive or repeated ORM traversal in templates.

Move complex presentation logic to appropriate helpers without moving
authorization decisions into templates.

---

# 16. Signals, Tasks and Side Effects

Signals create implicit control flow and should be used conservatively.

Before adding a signal, prefer an explicit call when the workflow is
local and known.

For existing signals:

- identify all senders and receivers;
- test observable side effects;
- avoid duplicate registration;
- consider transaction timing;
- avoid recursive save behavior;
- ensure idempotency where delivery may repeat.

Background tasks should be:

- idempotent where practical;
- explicit about retry behavior;
- safe against duplicate execution;
- careful with stale model instances;
- observable through structured logs or metrics;
- invoked after transaction commit when appropriate.

Do not call real external services from unit tests.

---

# 17. Test Strategy

Tests must verify behavior, not merely execute code.

Recommended test layers:

1. pure Python unit tests for framework-independent logic;
2. model and service tests;
3. form and serializer validation tests;
4. view/API tests using Django test utilities;
5. integration tests for database and external boundaries;
6. browser tests only for behavior requiring a real browser.

Django's test client is appropriate for testing requests, responses,
templates, redirects and context, but it is not a replacement for a
real-browser tool when JavaScript behavior is under test.

## Preserve tests covering

- business rules;
- permissions and authorization;
- authentication flows;
- boundary conditions;
- regressions;
- model constraints;
- transaction behavior;
- error handling;
- invariants;
- public URLs and API contracts;
- security-sensitive behavior;
- task idempotency;
- integration boundaries.

## Test database selection

For tests that access the database:

- with pytest, use the configured `db` or `django_db` facilities;
- with Django's runner, use `django.test.TestCase` when transactional
  isolation is required;
- use `TransactionTestCase` only when real transaction behavior must be
  tested;
- do not use plain `unittest.TestCase` for tests that depend on database
  state.

## Test organization

As a test suite grows, prefer:

    tests/
        test_models.py
        test_services.py
        test_forms.py
        test_views.py
        test_api.py
        test_tasks.py

Do not create one test file per tiny function if that makes navigation
worse.

Follow existing repository conventions.

---

# 18. Test Cleanup Policy

Test code must be refactored with the same care as production code.

Look for:

- duplicate scenarios;
- duplicate factories and fixtures;
- fixtures with excessive implicit data;
- tests with no meaningful assertions;
- assertions unrelated to the behavior under test;
- implementation-detail assertions;
- unnecessary patching;
- ORM mocking that makes tests unrealistic;
- tests dependent on execution order;
- tests dependent on current date, locale or timezone;
- tests that call external systems;
- repeated setup obscuring intent;
- redundant framework tests.

## Removing or consolidating tests

Never remove a test merely because it fails after refactoring.

For every removed or consolidated test, identify:

1. the behavior it verified;
2. the remaining test that verifies the same behavior;
3. why no unique boundary, regression or contract coverage was lost.

If no remaining test covers the behavior, preserve or replace the test.

## Mocking

Mock at external boundaries, not indiscriminately inside the code under
test.

Good mocking candidates include:

- remote HTTP services;
- email gateways;
- object storage;
- queues;
- clock or randomness when deterministic behavior is required.

Avoid mocking:

- ordinary model behavior;
- QuerySets purely to avoid using the test database;
- the exact internal sequence of private method calls;
- code owned by the project when a behavioral test is clearer.

A test that passes only because all meaningful collaborators were
mocked provides weak regression protection.

## Coverage

Coverage is an indicator, not the objective.

Do not:

- add meaningless assertions;
- execute lines without checking results;
- duplicate tests to inflate metrics;
- weaken assertions to make a refactoring pass;
- exclude difficult modules without justification.

Where configured, evaluate:

- line coverage;
- branch coverage;
- mutation testing.

For changed code, prioritize meaningful behavioral coverage over an
arbitrary global percentage.

---

# 19. Determinism in Tests

Tests must be repeatable.

Control where relevant:

- current time;
- time zones;
- random values;
- UUID generation;
- environment variables;
- filesystem paths;
- external services;
- ordering without an explicit `order_by`;
- asynchronous task execution;
- cache state.

Use timezone-aware datetimes.

Do not rely on the database returning rows in implicit order.

Clear or isolate cache state when tests depend on it.

Prevent test settings from accidentally connecting to production
databases, caches, queues or third-party services.

---

# 20. Performance and ORM Review

When a change affects data access, inspect for:

- N+1 queries;
- duplicate queries;
- loading unnecessary columns;
- unbounded QuerySets;
- missing pagination;
- repeated `.exists()`, `.count()` or iteration;
- evaluation of the same QuerySet multiple times;
- large `IN` clauses;
- per-row writes;
- missing indexes for demonstrated query patterns;
- long transactions;
- template-triggered queries.

Do not optimize from intuition alone when the change adds complexity.

Use evidence such as:

- query-count tests;
- SQL inspection;
- execution plans;
- profiling;
- production telemetry.

Preserve correctness before optimizing.

---

# 21. Static Analysis and Type Checking

Use the tools already configured by the repository.

If Ruff is used:

    ruff check .
    ruff format --check .

Run automatic fixes only when explicitly editing:

    ruff check --fix .
    ruff format .

Review all automatic changes.

Do not combine repository-wide formatting with a functional change.

If mypy and `django-stubs` are configured:

    mypy .

Do not silence type errors globally to complete a task.

Prefer:

- correcting the type;
- narrowing the ignore scope;
- adding a specific error code;
- documenting why the ignore is required.

Do not introduce `Any` merely to suppress a legitimate design issue.

Type checking is complementary to runtime tests and does not replace
them.

---

# 22. Security Rules

Treat all external input as untrusted.

Review where applicable:

- authentication;
- authorization;
- object ownership;
- CSRF;
- XSS;
- SQL injection;
- command injection;
- path traversal;
- unsafe deserialization;
- file uploads;
- open redirects;
- SSRF;
- sensitive logging;
- secret handling;
- rate limiting;
- session security.

## Mandatory rules

Never introduce secrets into:

- source code;
- settings committed to version control;
- tests;
- fixtures;
- logs;
- documentation;
- Docker images.

Never enable `DEBUG` in production.

Do not broadly add `@csrf_exempt`.

Do not use string interpolation to build raw SQL.

Do not use `mark_safe` with untrusted content.

Do not log:

- passwords;
- authentication tokens;
- session identifiers;
- secret keys;
- sensitive personal data.

Authorization must be tested separately from authentication.

For object-level access, test that one user cannot access or modify
another user's resources.

Run the deployment check using production-equivalent settings before a
production release:

    python manage.py check --deploy

---

# 23. Settings and Environment Rules

Preserve separation between environments.

Typical settings modules:

    config.settings.base
    config.settings.local
    config.settings.test
    config.settings.production

Do not read environment variables throughout arbitrary application
modules.

Centralize environment configuration in settings or in the project's
established configuration layer.

Required production behavior includes:

- `DEBUG = False`;
- secret keys outside source control;
- explicit allowed hosts;
- secure cookie settings where applicable;
- HTTPS-related settings appropriate to the deployment;
- error reporting;
- production-ready WSGI or ASGI server;
- correct static and media file handling.

Do not use `runserver` as the production server.

Do not copy production credentials into local or test settings.

---

# 24. Dependency Policy

Before adding a dependency:

1. check whether the standard library solves the problem;
2. check whether Django already provides the capability;
3. check whether an existing project dependency solves it;
4. verify compatibility with the supported Python and Django versions;
5. assess maintenance and security implications;
6. justify the additional operational cost.

Do not add a large package for a small local problem.

Do not upgrade unrelated dependencies during a feature or bug fix.

Do not manually edit a lock file.

Remove a dependency only after proving that it is unused by:

- production code;
- settings;
- templates;
- management commands;
- migrations;
- plugins;
- tests;
- scripts;
- deployment configuration.

---

# 25. Error Handling and Logging

Do not silently swallow exceptions.

Avoid:

    except Exception:
        pass

Catch the narrowest exception that can be handled meaningfully.

Preserve exception context unless deliberately translating an exception
at an architectural boundary.

User-facing errors must not expose:

- stack traces;
- SQL;
- file paths;
- secrets;
- internal configuration.

Use structured logging when supported by the project.

Add useful context without logging sensitive data.

Do not turn programmer errors into apparently successful HTTP
responses.

---

# 26. Code Deletion Policy

Deletion is encouraged when it clearly reduces complexity.

Before deleting code, search for usage in:

- Python imports;
- URL configuration;
- settings;
- `INSTALLED_APPS`;
- middleware configuration;
- templates;
- template tags;
- admin registration;
- signals;
- management commands;
- Celery task discovery;
- migrations;
- serializers;
- reflection;
- dynamic imports;
- tests;
- external/public API contracts.

Be careful with dynamically discovered Django components.

If usage cannot be reliably established, retain the code and report it
as suspected dead code.

---

# 27. REVIEW Mode

After implementation or stabilization, perform a separate review pass.

Review the final diff as if it were written by another developer.

Look specifically for:

1. unintended behavior changes;
2. accidental HTTP contract changes;
3. permission or authorization regressions;
4. migration risks;
5. lost behavioral coverage;
6. tests passing for the wrong reason;
7. mocks hiding defects;
8. N+1 query regressions;
9. incorrect transaction boundaries;
10. unsafe signal side effects;
11. invalid timezone assumptions;
12. security regressions;
13. leaked secrets or sensitive logs;
14. unnecessary abstractions;
15. accidental dependency changes;
16. unrelated formatting;
17. generated or temporary files;
18. code that should have been deleted instead of generalized.

Fix only confirmed issues.

Do not broaden the scope merely because additional improvements are
possible.

---

# 28. Final Verification

Before declaring completion, execute the checks applicable to the
change.

Minimum verification:

    ruff format --check .
    ruff check .
    python manage.py check
    python manage.py makemigrations --check --dry-run
    focused tests

When configured:

    mypy .

Before integration:

    complete test suite
    integration tests
    coverage checks
    dependency/security scan
    production deployment check
    build/package validation

Do not claim that a test, linter or build passed unless it was executed.

If a command cannot run because of environment limitations, report:

- the exact command;
- the reason it could not run;
- which parts of the change remain unverified.

---

# 29. Git Diff Review

Before finishing, inspect:

    git status --short
    git diff --check
    git diff

Also inspect staged changes when applicable:

    git diff --cached

Check for:

- unrelated files;
- debug statements;
- commented-out code;
- temporary test skips;
- weakened assertions;
- accidental migration files;
- missing migration files;
- settings changes;
- lock-file churn;
- secrets;
- generated files;
- API changes;
- formatting churn;
- obsolete imports.

The final diff should contain only changes directly contributing to the
task.

---

# 30. Stop Conditions

Stop refactoring when:

- externally observable behavior is preserved;
- tests express behavior clearly;
- meaningful duplication has been addressed;
- dead code proven safe to delete has been removed;
- remaining abstractions have clear responsibilities;
- applicable static checks pass;
- Django system checks pass;
- migration state is consistent;
- further changes would be mainly stylistic;
- additional cleanup would materially increase risk.

Do not pursue theoretical architectural purity.

Do not refactor stable Django conventions into custom frameworks.

A smaller, explicit and understandable solution is preferable to a
generic but more complex architecture.

---

# 31. Required Final Report

Provide a concise final report with the following structure.

## Summary

Describe what changed and why.

## Simplifications

List:

- code removed;
- duplication eliminated;
- abstractions simplified;
- signals or side effects made explicit;
- dependencies removed;
- query behavior improved.

## Database and migrations

State:

- whether models changed;
- whether migrations were created;
- whether migration drift was checked;
- migration risks, if any.

## Tests

List:

- tests added;
- tests modified;
- tests consolidated;
- tests removed;
- where equivalent behavioral coverage remains.

## Verification

List only commands actually executed.

Example:

    PASS  ruff format --check .
    PASS  ruff check .
    PASS  python manage.py check
    PASS  python manage.py makemigrations --check --dry-run
    PASS  pytest apps/orders/tests -q
    PASS  pytest
    PASS  mypy .

When a check fails:

    FAIL  <command>
          <concise reason>

When a check cannot be executed:

    NOT RUN  <command>
             <reason>

Never fabricate execution results.

## Remaining issues

List confirmed issues deliberately left unchanged.

## Residual risks

Describe any remaining:

- behavioral risk;
- migration risk;
- security risk;
- performance risk;
- compatibility risk;
- unverified area.

---

# 32. Golden Rules

When uncertain:

    Understand before editing.

    Preserve behavior unless explicitly asked to change it.

    Make the smallest correct change.

    Prefer deletion over unnecessary abstraction.

    Prefer Django conventions over custom infrastructure.

    Do not add repository layers that merely mirror the ORM.

    Keep HTTP, business and persistence responsibilities explicit.

    Validation does not replace authorization.

    Tests verify behavior, not implementation details.

    Never weaken a valid test merely to make it pass.

    Coverage is evidence, not the objective.

    Mock external boundaries, not the entire application.

    Treat migrations as production code.

    Inspect generated migrations.

    Never expose secrets or enable DEBUG in production.

    Never claim verification that was not executed.

    Review the complete diff as if another developer wrote it.

    Stop when further refactoring provides little concrete value.
``