# Deployment

## Environment model

### Local

- Python application
- local SQLite or MySQL
- optional object storage emulator
- seeded development data

### Staging

- self-hosted application
- MySQL
- Redis
- object storage
- isolated secrets and database

### Production

- same topology as staging
- backups enabled
- restore drills performed regularly

## Configuration

Use `.env` locally and a secret manager for staging and production.

Key variables include:

- `DATABASE_URL`
- `APP_ENV`
- `RUNTIME_SCHEMA_COMPAT`
- `HOLIDAY_SOURCE_URL`
- `WORKING_WEEK`
- `STAGE_STEPS_CSV_PATH`

## Database

Primary target is MySQL 8.

Example connection style:

```text
mysql+pymysql://...
```

SQLite is currently supported for local smoke testing.

Initialise local schema and seeds with:

```bash
alembic upgrade head
PYTHONPATH=. python scripts/seed_dev_data.py
```

Seed reference data directly:

```bash
PYTHONPATH=. python scripts/seed_reference_data.py
```

Reference data defaults to `app/seeds/stage_steps_hours.csv` and can be overridden with `STAGE_STEPS_CSV_PATH` for local imports.

`scripts/init_db.py` remains available as a local-only reset helper (drop/recreate through Alembic + seed). It must not be used as a production migration mechanism.

## Backup and restore guidance

- nightly full backups
- binlog or point-in-time recovery for MySQL
- quarterly restore simulation into staging
- documented restore runbook with RTO and RPO targets

## Safe deploy and rollback

Suggested pattern:

1. run migrations
2. deploy the app
3. flip traffic
4. roll back the app binary if needed

Backward-compatible migrations are preferred for low-risk deploys.

Startup policy:

- all normal environments should run with `RUNTIME_SCHEMA_COMPAT=false`
- app startup fails fast if the database is not at Alembic head when compatibility mode is disabled
- startup must not mutate schema in staging/production
- `RUNTIME_SCHEMA_COMPAT=true` is local/dev-only legacy compatibility for old pre-Alembic databases
- staging/production must not use sqlite `DATABASE_URL`
- staging/production must provide non-default `SECRET_KEY`
- staging/production must have stage/step reference data in DB (seeded) or provide a valid `STAGE_STEPS_CSV_PATH`

## Current deployment caveats

- MySQL-specific indexing strategy is still listed as future work
- authorisation hardening is not yet complete, so production exposure should be controlled carefully
