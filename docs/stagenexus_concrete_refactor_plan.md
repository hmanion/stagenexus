# StageNexus Concrete Refactor Plan

## Objective
Refactor StageNexus from a strong prototype into a maintainable, production-capable internal operations app without disrupting the domain model that already appears valuable.

This plan assumes the current priority is **hardening and restructuring**, not inventing major new workflow concepts.

---

## Refactor goals

1. Make releases safe and repeatable.
2. Make authorization consistent and enforceable.
3. Reduce coupling in the backend.
4. Add the asynchronous architecture needed for operational workflows.
5. Build enough test coverage to change the system safely.
6. Prepare the UI and reporting layer for real internal adoption.

---

## Guiding principles

- Preserve working business rules unless there is a clear reason to change them.
- Refactor structure before expanding scope.
- Move risky logic out of routes and into testable services.
- Prefer incremental hardening over large rewrites.
- Keep SQLite as local-only convenience, but treat MySQL as the real target platform, as set out in the deployment notes.
- Align implementation to the documented target topology of app + MySQL + Redis + object storage.

---

## Recommended delivery structure

Run the refactor in **6 workstreams** across **4 phases**.

### Workstreams
1. Schema and data lifecycle
2. Authorization and security
3. Backend modularization
4. Jobs and workflow automation
5. Test and quality engineering
6. UI, reporting, and operational visibility

---

# Phase 1: Stabilize the foundation
**Goal:** remove the most serious production blockers without changing the app’s core behaviour.

## 1. Schema and data lifecycle
### Tasks
- Introduce Alembic and create a real migration baseline.
- Convert current schema creation into tracked migrations.
- Stop treating runtime schema repair as a normal structural upgrade path.
- Split local bootstrap from migration execution.
- Define migration rules for backward-compatible deploys.

### Deliverables
- `alembic/` migration setup
- Baseline migration matching current production-intended schema
- Local developer commands for `migrate`, `upgrade`, `downgrade`, `seed`
- Written migration policy for deploys and rollbacks

### Exit criteria
- Schema changes no longer rely on startup repair.
- Staging can be upgraded via migrations only.
- Developers can recreate a working environment without hand-editing the schema.

---

## 2. Authorization and security
### Tasks
- Define a canonical permission model from the documented ownership rules.
- Create centralized authorization dependencies/policies for FastAPI.
- Remove ad hoc access checks from route handlers.
- Protect approval, readiness, campaign generation, and update endpoints first.
- Add audit-friendly actor capture for sensitive transitions.

### Deliverables
- `auth/policies.py` or equivalent policy layer
- Role + ownership access matrix
- Shared route guards/dependencies
- Forbidden-path tests for protected actions

### Exit criteria
- No sensitive endpoint relies on informal caller behaviour.
- Permissions are enforced consistently by role and ownership.
- Approval actions are traceable to actor identity and role.

---

## 3. Configuration cleanup
### Tasks
- Remove machine-specific and file-path-specific assumptions.
- Move operational config to env vars, seeded records, or admin-managed data.
- Separate local dev defaults from staging/production config.
- Validate startup config explicitly and fail fast on missing critical settings.

### Deliverables
- Clean `settings` model with environment validation
- Example env files for local/staging/prod
- Removal of hardcoded local path dependencies

### Exit criteria
- New developers can run the app without editing source files.
- Staging/prod settings come only from environment or managed secrets.

---

# Phase 2: Restructure the backend
**Goal:** reduce coupling and make core logic easier to test and maintain.

## 4. Route and service decomposition
### Tasks
- Break the oversized route layer into bounded modules.
- Separate transport logic, orchestration, and domain logic.
- Define clear application-service boundaries.
- Remove duplicated validation or business checks from routes.

### Suggested module split
- `deals`
- `campaigns`
- `deliverables`
- `workflow`
- `sow_changes`
- `capacity`
- `risks`
- `dashboard`
- `admin/reference_data`

### Deliverables
- Smaller route modules by domain area
- Service layer with explicit inputs/outputs
- Reduced import sprawl in API packages
- Consistent error handling patterns

### Exit criteria
- Route handlers are thin and mostly orchestration-free.
- Domain rules live in services or policy layers, not scattered through endpoints.
- New features can be added without expanding a single central route file.

---

## 5. Canonical domain vocabulary
### Tasks
- Resolve naming drift between Scope/Deal, Stage/Sprint/Module, Step/Workflow Step.
- Choose one canonical set of internal terms.
- Map alternative terms only where genuinely needed.
- Align docs, schemas, API names, database comments, and UI labels.

### Deliverables
- Domain glossary
- Refactor map of old term -> new term
- Compatibility notes for any API or UI naming changes

### Exit criteria
- The same object is not described three different ways across docs and code.
- Product, engineering, and operations use the same vocabulary.

---

## 6. Transaction and persistence hardening
### Tasks
- Review write-heavy flows for transaction safety.
- Add explicit transaction boundaries for campaign generation, approvals, and readiness updates.
- Design MySQL indexes around real query paths.
- Validate idempotency for endpoints that may be retried.

### Deliverables
- Transaction design notes for critical flows
- MySQL index plan
- Retry-safe write behaviour for critical state transitions

### Exit criteria
- Campaign generation and approvals behave correctly under concurrency.
- MySQL performance is acceptable in staging.
- Duplicate requests do not create invalid duplicate outcomes.

---

# Phase 3: Add operational architecture
**Goal:** support real workflow automation, reliability, and observability.

## 7. Background jobs and eventing
### Tasks
- Introduce a job runner using the already-planned Redis-backed environment.
- Move dependency recalculation, reminders, and notifications out of request/response flows.
- Define domain events for key transitions.
- Add retry policies, dead-letter handling, and operator visibility.

### Candidate jobs
- Workflow dependency recalculation
- Risk escalation evaluation
- Notification/reminder sending
- Capacity refresh/rebuild
- Scheduled health checks

### Deliverables
- Worker process and queue config
- Job definitions for the highest-value async work
- Job monitoring and failure logging

### Exit criteria
- Expensive or time-based actions no longer depend on synchronous API calls.
- Failed jobs are visible and retryable.
- Workflow updates remain consistent after dependent changes.

---

## 8. Observability and auditability
### Tasks
- Add structured logging for major lifecycle actions.
- Add metrics for API failures, queue failures, and slow endpoints.
- Add audit records for approvals, state transitions, assignments, and readiness actions.
- Define alerting for production-critical failures.

### Deliverables
- Structured log format
- Audit trail model or event log
- Basic monitoring dashboard
- Alert definitions for critical job/API failures

### Exit criteria
- Support issues can be diagnosed from logs and audit trails.
- Sensitive actions are attributable.
- Operators can see broken jobs or rising error rates quickly.

---

## 9. Backup, restore, and deployment discipline
### Tasks
- Turn the documented backup/restore guidance into executable runbooks.
- Test restore into staging.
- Add deployment checklists around migrations and rollback compatibility.
- Validate zero-downtime expectations for compatible releases.

### Deliverables
- Restore runbook
- Release checklist
- Staging restore drill record
- Rollback procedure linked to migration policy

### Exit criteria
- Restore has been rehearsed successfully.
- Deployment steps are repeatable and documented.
- Rollback paths are realistic, not theoretical.

---

# Phase 4: Strengthen product usability
**Goal:** make the app dependable for day-to-day internal use.

## 10. Test strategy expansion
### Tasks
- Add unit tests for rule-heavy services.
- Add integration tests for lifecycle endpoints.
- Add regression tests for calendar and generation behaviour.
- Add permission tests for protected operations.
- Add staging smoke tests against MySQL.

### Highest-priority test targets
- Readiness gate before campaign generation
- Dual-approval SOW change activation
- Publish readiness actor tracking
- Campaign health guardrail
- Working-day date calculation
- Publish-step dedupe/reconciliation

### Deliverables
- Test pyramid by layer
- Seeded fixtures/factories
- CI test workflow
- Minimum coverage thresholds for critical packages

### Exit criteria
- Critical domain flows are protected by automated tests.
- Refactors can be made with low fear of silent regression.

---

## 11. Frontend hardening
### Tasks
- Decide whether the current UI path is transitional or long-term.
- Replace demo-style shells with production-quality screens.
- Build consistent forms, tables, filtering, validation feedback, and permission-aware controls.
- Add operational views for risks, approvals, health, and capacity.

### Deliverables
- Frontend architecture decision
- Screen inventory with priority order
- Production-ready UI for the top operational workflows
- Shared design patterns for states, errors, and permissions

### Exit criteria
- Core user journeys can be completed reliably without developer assistance.
- UI reflects real operational roles and permissions.
- The frontend no longer feels like a prototype wrapper around the backend.

---

## 12. Dashboard and reporting layer
### Tasks
- Build summary endpoints and views for health, risk, capacity, and approvals.
- Ensure dashboard logic aligns with locked operational rules.
- Expose enough visibility to reduce spreadsheet fallback.

### Deliverables
- Dashboard API endpoints
- Management views for campaign health and risk
- Capacity visibility by team/role
- Publish readiness and bottleneck reporting

### Exit criteria
- Team leads can monitor operational state without querying raw records.
- Core management reporting can happen inside the app.

---

# Suggested implementation order

## Sprint 1–2
- Alembic baseline and migration workflow
- Centralized authorization model
- Config cleanup

## Sprint 3–4
- Route decomposition
- Service boundary refactor
- Domain vocabulary lock
- Transaction review for critical flows

## Sprint 5–6
- Background jobs
- Observability and audit trail
- MySQL indexing and staging hardening

## Sprint 7–8
- Test suite expansion
- Frontend hardening for top workflows
- Dashboard/reporting first pass

---

# Team structure suggestion

## If one developer
Work in this order:
1. Migrations
2. Authorization
3. Route/service refactor
4. Tests
5. Jobs
6. UI hardening

## If two developers
- Developer A: schema, backend modularization, jobs, MySQL hardening
- Developer B: authorization, tests, frontend, dashboards

## If three or more developers
Run workstreams in parallel, but keep one owner over:
- migration strategy
- vocabulary and model consistency
- authorization rules

---

# What not to refactor yet

Avoid these until the hardening work is in place:
- Major redesign of the core campaign model
- Broad feature expansion into new workflow areas
- Cosmetic frontend rewrite without backend/service stabilization
- Premature optimization outside known MySQL bottlenecks

---

# Definition of done for the refactor

I would consider this refactor successful when all of the following are true:

- Deployments use real migrations, not schema repair.
- Authorization is centralized and tested.
- Critical domain logic sits in services with strong tests.
- Async workflow updates and reminders run through jobs.
- MySQL staging behaves like a realistic production rehearsal.
- Logs, auditability, and restore procedures exist and have been exercised.
- The frontend supports real day-to-day operational use.

---

# Bottom line

The right refactor is not a rewrite. It is a **controlled hardening program**.

The business model already looks valuable. The task now is to make the codebase safer to change, safer to deploy, and easier to operate.

