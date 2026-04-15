# Deployment Model

## Environments
- Local: Python app + local SQLite/MySQL, object storage emulator, seeded data.
- Staging: self-hosted app + MySQL + Redis + object storage, isolated secrets and DB.
- Production: same topology as staging with backups and restore drills.

## Configuration
- Environment variables from `.env` (local) and secret manager (staging/prod).
- Main variables: `DATABASE_URL`, `HOLIDAY_SOURCE_URL`, `WORKING_WEEK`.

## Database
- Primary target: MySQL 8 (`mysql+pymysql://...`).
- Current scaffold supports SQLite for local smoke testing.
- Initialize schema and seeds:
  - `PYTHONPATH=. python scripts/init_db.py`

## Backup/restore guidance
- Nightly full backups + binlog/PITR for MySQL.
- Quarterly restore simulation into staging.
- Keep restore runbook with RTO/RPO targets.

## Safe deploy/rollback
- Deploy app first in compatibility mode.
- Run migrations.
- Flip traffic.
- Roll back app binary if needed; use backward-compatible migrations for zero-downtime transitions.
