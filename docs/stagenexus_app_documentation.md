# StageNexus App Documentation

## 1. Overview

**StageNexus** is a FastAPI-based campaign operations backend for Today Digital. The repository positions it as a purpose-built operations system for managing the lifecycle from commercial agreement through campaign execution, using the core model:

**Deal -> Campaign -> Sprint -> Module -> Deliverable -> Workflow Step**

The current app is implemented in Python rather than Laravel, but the repo explicitly keeps the architecture framework-agnostic so it can later migrate to Laravel if needed.

## 2. What the app currently does

The repo and project notes show that the app already supports:

- deal creation, submission, ops approval, and campaign generation
- campaign, sprint, module, deliverable, and workflow-step data structures
- a working-day timeline engine based on a **Mon-Thu** working week
- England/Wales bank holiday support using the GOV.UK holiday feed
- separate **system risks** and **manual risks**
- a capacity ledger with warning and override flows
- an operational readiness gate before campaigns can be generated
- template version pinning during campaign generation
- deliverable workflow transitions including a `ready_to_publish` state
- SOW change requests with parallel approval by Head Ops and Head Sales
- a work queue, escalations, and role-based dashboard endpoints

## 3. Technical stack

### Backend
- **FastAPI** application entrypoint in `app/main.py`
- **SQLAlchemy 2.x** ORM for persistence
- **Pydantic 2.x** schemas for API validation
- **Uvicorn** for local serving
- **PyMySQL** support for MySQL 8
- **Alembic** is present as a dependency, though the notes suggest migration history is not yet fully in place

### Runtime behavior
At startup, the app:
- creates database tables from metadata
- applies runtime schema updates
- validates SQLite foreign key support when relevant
- performs runtime integrity checks

### Frontend / UI
The repo includes:
- `app/ui`
- `app/static`
- a demo UI mounted at `/`
- OpenAPI/Swagger docs at `/docs`

This indicates the current codebase is primarily backend-first, with a lightweight UI layer for testing and operations access.

## 4. Repository structure

Top-level structure observed in the repo:

- `.codex` — project/codex support files
- `app` — main application package
- `docs` — supporting project documentation
- `scripts` — setup and backfill scripts
- `tests` — test suite
- `.env.example` — local environment template
- `requirements.txt` — Python dependencies
- `README.md` — quick start and API starter list

### `app` package structure
The application package is organised into:

- `app/api` — API routes
- `app/core` — core application logic/config helpers
- `app/db` — database setup and runtime schema support
- `app/models` — SQLAlchemy domain models
- `app/schemas` — request/response models
- `app/seeds` — seeded reference data
- `app/services` — business logic and orchestration
- `app/static` — static assets
- `app/ui` — demo UI routes/views
- `app/workflows` — workflow definitions
- `app/main.py` — FastAPI app bootstrap

### Notable service modules
The service layer is substantial and suggests the app’s core rules live outside the route layer. Observed services include:

- `authz_service.py`
- `calendar_service.py`
- `campaign_generation_service.py`
- `campaign_health_service.py`
- `capacity_override_service.py`
- `capacity_service.py`
- `change_control_service.py`
- `deal_service.py`
- `deliverable_workflow_service.py`
- `my_work_queue_service.py`
- `ops_defaults_service.py`
- `ops_job_service.py`
- `risk_service.py`
- `stage_integrity_service.py`
- `timeline_health_service.py`
- `timeline_service.py`
- `workflow_engine_service.py`

This is a good sign: the codebase appears to separate HTTP transport from operational logic.

## 5. Core domain model

The documentation and model names indicate a campaign operations domain built around a structured delivery hierarchy.

### Main hierarchy
1. **Deal**
   - commercial scope / pre-delivery setup
   - owned by AM during early lifecycle
   - must pass readiness before campaigns are generated

2. **Campaign**
   - generated from a deal after readiness approval
   - pinned to a template version
   - assigned operational ownership, typically CM-led

3. **Sprint / Stage**
   - time-based delivery segments inside campaigns
   - used for planning, health tracking, and sequencing

4. **Module**
   - enabled product or operational components within campaigns/sprints

5. **Deliverable**
   - actual outputs such as content items or campaign assets
   - one deliverable maps to one publication

6. **Workflow Step**
   - granular execution tasks, approvals, and due-date controlled work

### Other model families visible in the repo
The route imports and domain model references indicate support for:

- clients and client contacts
- users, roles, teams, and app access roles
- campaign assignments
- milestones
- review windows and review rounds
- comments and notes
- benchmark targets and performance results
- manual and system risks
- escalations
- SOW change requests and approvals
- activity logs and audit-style records
- capacity ledgers and effort/dependency records for workflow steps

## 6. Working rules and operational logic

### Calendar logic
The app uses a working calendar with these current defaults:

- working week: **Monday to Thursday**
- holiday source: **GOV.UK bank holidays**
- no weekend end or due dates

This is not just documentation; it is reflected in both the repo notes and the environment configuration.

### Status and health
The working context defines the current global status options as:

- Not started
- In Progress
- On Hold
- Blocked: Client
- Blocked: Internal
- Blocked: Dependency
- Done
- Cancelled

Global health options are:

- Not due
- On Track
- At Risk
- Off Track

A campaign health guardrail is also documented: if any stage is **Off Track**, the campaign cannot be marked **On Track**.

### Ownership rules
Current locked rules include:

- one owner per object
- campaign owner is the assigned CM
- participants are not owners
- assignment pools are team-based:
  - AM -> Sales
  - CC/CCS -> Editorial
  - DN/MM -> Marketing
  - CM -> Client Services

### Readiness and control rules
The app enforces several important gates:

- campaign generation is blocked until the operational readiness gate passes
- one deliverable must belong to one publication
- mid-campaign SOW changes activate only after both required approvers approve
- deliverable readiness to publish records actor context

## 7. API design

The API is mounted under `/api` and grouped under a `campaign-ops` router.

### Confirmed starter / key endpoints
From the repo README and route file, the current API includes at least:

#### Health and startup
- `GET /health`

#### Deals / scopes
- `POST /api/deals`
- `POST /api/deals/{deal_id}/submit`
- `POST /api/deals/{deal_id}/ops-approve`
- `POST /api/deals/{deal_id}/generate-campaigns`

The route file also preserves compatibility aliases using `/scopes` alongside `/deals`, which suggests the codebase is transitioning naming from “scope” to “deal”.

#### Campaigns
- `GET /api/campaigns/{campaign_id}`
- `GET /api/campaigns/health`
- dashboard and campaign health related endpoints

#### Deliverables and workflow
- `POST /api/deliverables/{deliverable_id}/ready-to-publish`
- `POST /api/deliverables/{deliverable_id}/transition`
- `GET /api/deliverables/{deliverable_id}/history`
- `POST /api/workflow-steps/{step_id}/complete`
- `POST /api/workflow-steps/{step_id}/override-due`

#### Capacity and jobs
- `POST /api/jobs/run-ops-risk-capacity`
- `GET /api/capacity-ledger`
- `POST /api/capacity-ledger/{capacity_id}/request-override`
- `POST /api/capacity-ledger/{capacity_id}/decide-override`

#### Risks and escalations
- `GET /api/risks/system`
- `GET /api/risks/manual`
- `POST /api/risks/manual`
- `PATCH /api/risks/manual/{risk_id}`
- `GET /api/escalations`
- `POST /api/escalations/{escalation_id}/resolve`

#### Work queue and dashboards
- `GET /api/users/{user_id}/work-queue`
- `GET /api/dashboard/role`

#### Change control
- `POST /api/campaigns/{campaign_id}/sow-change-requests`
- `POST /api/sow-change-requests/{request_id}/decide`

### Authorization pattern
The route layer uses an `AuthzService`, and route snippets show role/ownership checks such as:

- AM or admin for creating deals
- deal owner or privileged role for submitting deals
- restricted approval/generation permissions for ops and leadership flows

The implementation notes still list **strong authorization middleware by role/ownership** as work remaining, so authorization exists but is not yet considered complete.

## 8. Example operational flow

A typical intended flow appears to be:

1. **Create deal**
   - AM creates a new deal/scope with client, dates, objective, positioning, and product lines.

2. **Submit deal**
   - deal moves from draft toward operational review.

3. **Ops approve**
   - Head Ops approval assigns operational roles such as CM and CC and validates readiness.

4. **Generate campaigns**
   - once readiness passes, campaigns are generated from templates and pinned to template versions.

5. **Execute campaign delivery**
   - campaigns contain sprints, modules, deliverables, and workflow steps.

6. **Track risk, capacity, and health**
   - system and manual risks, escalations, and capacity pressure are monitored.

7. **Publish workflow**
   - deliverables can move through workflow states until they are marked ready to publish.

8. **Handle change control**
   - SOW changes are raised and must be approved by both required approvers before activation.

## 9. Local setup

### Prerequisites
- Python 3
- pip / virtual environment support
- optionally MySQL 8 for a more production-like local setup

### Quick start
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --port 8000
```

### Local URLs
- app/demo UI: `http://127.0.0.1:8000/`
- API docs: `http://127.0.0.1:8000/docs`

### Database initialisation
The deployment notes specify:
```bash
PYTHONPATH=. python scripts/init_db.py
```

Important note: `scripts/init_db.py` currently **drops and recreates** the local schema for rapid iteration.

### Backfill script
To bring older local data into line with the latest timeline/workflow rules:
```bash
PYTHONPATH=. .venv/bin/python scripts/backfill_recent_updates.py
```

This script normalises older sprint milestones, converts legacy KO/interview deliverables into sprint workflow steps, refreshes template pinning, and recomputes risk/capacity ledgers.

## 10. Configuration

The `.env.example` file shows the main runtime configuration:

- `APP_ENV=local`
- `APP_PORT=8000`
- `DATABASE_URL=sqlite:///./campaign_ops.db`
- `SECRET_KEY=replace-me`
- `HOLIDAY_SOURCE_URL=https://www.gov.uk/bank-holidays.json`
- `WORKING_WEEK=mon,tue,wed,thu`
- `SHOW_DEMO_RAIL=true`
- `DEMO_RAIL_ALLOWED_ROLES=head_ops,admin`

### Database modes
- **SQLite** is supported for local smoke testing
- **MySQL 8** is the stated primary target for staging/production

Example production database URL pattern:
```text
mysql+pymysql://user:password@127.0.0.1:3306/campaign_ops
```

## 11. Deployment model

The project’s deployment notes define three environments.

### Local
- Python app
- local SQLite or MySQL
- object storage emulator
- seeded data

### Staging
- self-hosted app
- MySQL
- Redis
- object storage
- isolated secrets and database

### Production
- same topology as staging
- backups and restore drills

### Deployment guidance
- keep env vars in `.env` locally and a secret manager in higher environments
- use app-first deployment in compatibility mode
- run migrations
- flip traffic
- roll back app binary if needed
- prefer backward-compatible migrations for zero-downtime transitions

### Backup / restore guidance
- nightly full backups
- binlog / point-in-time recovery for MySQL
- quarterly restore simulations into staging
- maintain RTO/RPO runbook

## 12. Current implementation status

### Implemented well enough to document as present
- core hierarchy and domain backbone
- readiness gate before campaign generation
- template version pinning
- separate risk channels
- capacity ledger and override metadata
- working-day calendar logic
- publish readiness endpoint with actor tracking
- dual-approval SOW change flow

### Explicitly still incomplete or next increment
According to implementation notes, the following remain:

- stronger authorization middleware by role/ownership
- full workflow dependency DAG persistence and recalculation jobs
- notification and reminder jobs
- richer dashboard endpoints and frontend UI
- full Alembic migration history
- MySQL-specific indexing strategy

## 13. Architectural assessment

### Strengths
- strong domain-first modelling
- clear separation between routes, schemas, models, and services
- operational rules are explicit rather than buried in UI logic
- deployment path already anticipates self-hosted staging/production
- compatibility aliasing (`scope` -> `deal`) suggests care for iterative change

### Current limitations
- large route file suggests API decomposition may be needed over time
- migration strategy appears partially scaffolded rather than fully productionised
- authorization is present but not yet fully hardened
- frontend is secondary to backend at this stage
- some planning language still coexists with implementation language, which may confuse future maintainers unless terminology is consolidated

## 14. Recommended documentation set for the repo

If you want the repo to feel complete for future development, these are the documents I would keep or add:

1. **README.md**
   - concise setup, environment, and API summary

2. **docs/architecture.md**
   - system components, package structure, database responsibilities, service boundaries

3. **docs/domain-model.md**
   - definitions for Deal, Campaign, Sprint, Module, Deliverable, Workflow Step, ownership and status rules

4. **docs/workflows.md**
   - deal-to-campaign lifecycle, publish readiness, SOW change approvals, risk/capacity jobs

5. **docs/deployment.md**
   - environment topology, secrets, backup/restore, migration and rollback process

6. **docs/api.md**
   - endpoint groups, auth expectations, example requests/responses

7. **docs/known-gaps.md**
   - what is implemented, what is intentionally deferred, and what is unstable

## 15. Concise summary

StageNexus is a backend-led campaign operations system for Today Digital built in FastAPI with SQLAlchemy, designed around a structured operational hierarchy and rules-driven delivery model. It already covers the most important foundations — deals, readiness, campaign generation, workflow, risk, capacity, change control, and calendar logic — and is far beyond a bare scaffold. The main remaining work is hardening: authorization, richer dashboards/UI, dependency recalculation, notifications, and production-grade migration/indexing strategy.
