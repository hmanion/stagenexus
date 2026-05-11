# Migrations

## Policy

- Alembic is the source of truth for structural schema changes.
- `app/db/schema_updates.py` is transitional compatibility debt and must not be extended for normal structural evolution.
- Staging and production must run migrations before app startup.
- Startup is expected to fail fast outside local/dev when the DB is not at Alembic head.

## Environment variables

- `DATABASE_URL`: single connection source for both app runtime and Alembic.
- `APP_ENV`: `local`, `dev`, `development`, `staging`, or `production`.
- `RUNTIME_SCHEMA_COMPAT`: defaults to `true` only in local/dev/development. Set `false` for staging/production.

## Local workflow

1. Upgrade schema:
   - `alembic upgrade head`
2. Seed development data:
   - `PYTHONPATH=. python scripts/seed_dev_data.py`
3. Optional local reset helper (drops and recreates schema):
   - `PYTHONPATH=. python scripts/init_db.py`
   - This helper is local-only and must not be used in staging/production.

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
- Upgrade and rollback paths are explicit and understandable.

## Rollback expectations

- Rollback support is best-effort and migration-specific.
- Prefer backward-compatible forward fixes for production incidents.
- Do not assume automatic zero-risk downgrades for destructive operations.
