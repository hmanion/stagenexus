# Roadmap and current gaps

## Already implemented

The current codebase already includes a meaningful operational backbone:

- explicit delivery hierarchy
- operational readiness gate
- template version pinning
- deliverable workflow states and publish readiness
- dual-approval SOW change flow
- separate manual and system risk channels
- capacity ledger with overrides
- working-day calendar service

## Gaps called out in project notes

### 1. Stronger authorisation
Role and ownership middleware still needs to be tightened.

### 2. Workflow dependency persistence
Full DAG persistence and recalculation support are not yet complete.

### 3. Notifications and reminders
Operational reminders and alerting jobs still need implementation.

### 4. Richer dashboards and frontend UI
The backend is ahead of the UI. Dashboard depth and frontend polish remain future work.

### 5. Migration maturity
Alembic migration history and MySQL-specific indexing strategy still need to be formalised.

## Practical next steps

### Near term

- add robust authz checks to every mutable route
- stabilise the domain schema and formalise migrations
- document all current endpoints from the live router
- add API examples for the remaining operational endpoints

### Medium term

- implement dependency graph persistence and recalculation
- add scheduled reminder and escalation jobs
- add richer dashboard and queue views
- improve audit and reporting visibility

### Longer term

- harden staging and production deployment playbooks
- add deeper test coverage around timeline, capacity, and change control
- decide whether the long-term target remains FastAPI or a migration path is still desired
