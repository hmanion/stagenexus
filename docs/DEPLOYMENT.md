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
- `HOLIDAY_SOURCE_URL`
- `WORKING_WEEK`

## Database

Primary target is MySQL 8.

Example connection style:

```text
mysql+pymysql://...
```

SQLite is currently supported for local smoke testing.

Initialise schema and seeds with:

```bash
PYTHONPATH=. python scripts/init_db.py
```

## Backup and restore guidance

- nightly full backups
- binlog or point-in-time recovery for MySQL
- quarterly restore simulation into staging
- documented restore runbook with RTO and RPO targets

## Safe deploy and rollback

Suggested pattern:

1. deploy the app in compatibility mode
2. run migrations
3. flip traffic
4. roll back the app binary if needed

Backward-compatible migrations are preferred for low-risk deploys.

## Current deployment caveats

- migration history does not yet appear fully formalised
- MySQL-specific indexing strategy is still listed as future work
- authorisation hardening is not yet complete, so production exposure should be controlled carefully
