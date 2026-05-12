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

## Progress since last broad docs baseline (2026-04-16, `b33f611`)

The following areas were previously called out as gaps and are now materially advanced:

- Authorization hardening:
  - Centralized actor resolution and control checks are now implemented through `AuthzService`.
  - Route-level enforcement and dedicated authz regression tests were added.
- Migration maturity:
  - Alembic baseline setup and migration policy are now in place.
  - Migration governance and Alembic-head startup checks are now the default path.
  - Runtime schema repair is limited to an explicit local/dev legacy compatibility mode.
- Frontend/documentation structure:
  - Static UI assets and template partials were split for maintainability.
  - Additional focused docs were added for authorization and migrations.
- Rule and governance test coverage:
  - New tests now cover authz, migration governance, campaign generation, timeline rules, capacity/risk, publishing, and SOW controls.

## Remaining gaps and active roadmap

### 1. Dependency persistence and recalculation depth
Full DAG persistence and recalculation behavior still needs to be completed and hardened.

### 2. Notifications and reminders
Operational reminders, escalations, and scheduled alerting jobs still need full implementation.

### 3. Richer dashboards and frontend UX
The backend remains ahead of the UI; dashboard depth, queue ergonomics, and frontend polish remain future work.

### 4. Production rollout confidence
Staging/production deployment playbooks, observability, and operational runbooks still need hardening.

## Practical next steps

### Near term

- close any remaining authz edge cases and keep endpoint-to-policy mapping current
- continue stabilising workflow dependency persistence and recalculation paths
- document all current endpoints from the live router
- add API examples for the remaining operational endpoints

### Medium term

- implement dependency graph persistence and recalculation
- add scheduled reminder and escalation jobs
- add richer dashboard and queue views
- improve audit and reporting visibility
- extend production-like migration smoke checks in CI/staging

### Longer term

- harden staging and production deployment playbooks
- add deeper test coverage around timeline, capacity, and change control
- decide whether the long-term target remains FastAPI or a migration path is still desired
