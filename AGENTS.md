# Repository Guidelines

## Project Structure & Module Organization

Application code lives in `app/`. Keep HTTP concerns in `app/api/routes`,
validated contracts in `app/schemas`, business operations in `app/services`,
database models and session setup in `app/db`, and shared configuration in
`app/core`. Alembic revisions live in `migrations/versions`. Tests mirror the
runtime boundaries under `tests/unit` and `tests/integration`. Local containers
are defined in `infra/local/compose.yaml`; project decisions and learning guides
belong in `docs/`.

## Build, Test, and Development Commands

- `uv sync --frozen --all-groups`: install the exact locked Python 3.14
  environment, including development tools.
- `uv run uvicorn app.main:app --reload`: run the API locally.
- `docker compose --env-file .env -f infra/local/compose.yaml up -d db`: start
  PostgreSQL.
- `uv run alembic upgrade head`: apply committed schema migrations.
- `uv run ruff check .` and `uv run ruff format --check .`: lint and verify
  formatting.
- `uv run mypy`: run strict type checking.
- `uv run pytest`: run tests; set `TEST_DATABASE_URL` to include PostgreSQL
  integration coverage.

## Coding Style & Naming Conventions

Use four-space indentation, an 88-character line limit, and Python 3.14 syntax.
Ruff enforces imports, upgrades, async rules, and common bug patterns; mypy runs
in strict mode. Use `snake_case` for modules, functions, and variables;
`PascalCase` for classes and Pydantic/ORM models; and descriptive test names such
as `test_concurrent_seed_requests_are_serialized`. Keep routes thin and pass an
`AsyncSession` into services rather than creating engines or committing there.

## Testing Guidelines

Pytest and pytest-asyncio are configured in `pyproject.toml`. Mark tests that
require PostgreSQL with `@pytest.mark.integration`; they must skip safely when
`TEST_DATABASE_URL` is absent and run against real PostgreSQL in CI. Add unit
tests for routing or pure decisions and integration tests for migrations,
constraints, transactions, and locking. Apply migrations instead of using
`Base.metadata.create_all()`.

## Commit & Pull Request Guidelines

Follow the existing imperative, sentence-case commit style: `Add Phase 1
foundation`, `Implement Phase 2 database foundation`. Keep commits focused and
avoid mixing unrelated cleanup. Work on `dev` and open PRs into protected
`main`. PR descriptions should explain the behavior and rationale, list
validation commands, call out migration or configuration changes, and link an
issue when applicable. All required `quality` checks and review conversations
must pass before merge.

## Security & Configuration

Copy `.env.example` to `.env`; never commit `.env`, credentials, database data,
or Terraform state. Seed/reset endpoints are intentionally unauthenticated but
must remain unavailable in `dev` and `prod`. Never expose a `local` or `test`
instance to an untrusted network.
