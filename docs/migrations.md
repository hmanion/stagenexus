# Migrations

## Policy

- Alembic is the source of truth for structural schema changes.
- `app/db/schema_updates.py` is transitional compatibility debt and must not be extended for normal structural evolution.
- All environments should run migrations before app startup.
- Startup is expected to fail fast when `RUNTIME_SCHEMA_COMPAT=false` and the DB is not at Alembic head.
- `RUNTIME_SCHEMA_COMPAT=true` is an explicit local/dev-only legacy escape hatch for old pre-Alembic databases.

## Environment variables

- `DATABASE_URL`: single connection source for both app runtime and Alembic.
- `APP_ENV`: `local`, `dev`, `development`, `staging`, or `production`.
- `RUNTIME_SCHEMA_COMPAT`: defaults to `false`. Only set `true` in local/dev/development when temporarily opening an old pre-Alembic database.

## Local workflow

1. Upgrade schema:
   - `alembic upgrade head`
2. Seed development data:
   - `PYTHONPATH=. python scripts/seed_dev_data.py`
3. Optional local reset helper (drops and recreates schema):
   - `PYTHONPATH=. python scripts/init_db.py`
   - This helper recreates schema through Alembic migrations, is local-only, and must not be used in staging/production.

## Creating a migration

1. Generate candidate migration:
   - `alembic revision --autogenerate -m "short_description"`
2. Review generated operations carefully:
   - confirm only intended tables/columns/indexes/constraints changed
   - remove accidental local-only artifacts
   - ensure non-destructive change strategy unless explicitly planned
3. Apply locally:
   - `alembic upgrade head`
4. Run tests and startup smoke checks before merge.

## Review checklist

- Migration is additive or explicitly safe for rollout.
- Indexes/constraints match model intent.
- No hidden schema mutation added to startup/runtime repair code.
- Runtime repair code is allowed only behind explicit local/dev compatibility mode and for data hygiene, such as removing empty optional stages and their milestones when older local data no longer matches module-driven generation rules.
- Upgrade and rollback paths are explicit and understandable.

## Rollback expectations

- Rollback support is best-effort and migration-specific.
- Prefer backward-compatible forward fixes for production incidents.
- Do not assume automatic zero-risk downgrades for destructive operations.
