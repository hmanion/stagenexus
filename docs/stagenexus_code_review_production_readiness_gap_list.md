# StageNexus Production-Readiness Gap List

## Overall judgement
StageNexus looks like a strong late-prototype or early-hardening internal operations app, but it still has several important gaps before it should be treated as production-ready. The biggest missing pieces are not in the business model itself. They are in the surrounding engineering controls: migrations, authorization, asynchronous processing, test depth, frontend maturity, and operational safety.

---

## Production-readiness summary

### Current state
**Not yet production-ready** for broad internal operational reliance.

### Closest description
A well-modelled internal operations backend scaffold with credible business rules, but still missing several control layers required for safe production deployment and maintainable scale.

---

## Gap list by priority

## 1. Critical gaps
These are the items most likely to block a safe real deployment.

### 1.1 Proper migration discipline is missing
**Gap**
The app still relies on prototype-style schema management rather than a formal migration lifecycle.

**Why it matters**
- Schema drift becomes likely across local, staging, and production.
- Rollbacks become difficult and risky.
- Real data becomes harder to protect during releases.

**Evidence**
- Alembic migration history is explicitly listed as still remaining. fileciteturn2file1L17-L18
- The deployment model assumes migrations as part of safe deploy/rollback, which means the current state is not yet aligned with the intended release process. fileciteturn2file0L18-L21
- Current setup still centers on direct schema initialization via script. fileciteturn2file0L10-L13

**What needs to change**
- Introduce full Alembic migration history.
- Remove structural runtime schema repair as a normal deployment mechanism.
- Define migration standards for forward and backward compatibility.

**Priority**
Critical

---

### 1.2 Strong authorization is not yet in place
**Gap**
Role- and ownership-based authorization is still unfinished.

**Why it matters**
- This is a direct production blocker for any multi-user operational app.
- Campaign, client, ownership, and approval data should not rely on informal access control.
- Security retrofits become harder once route sprawl increases.

**Evidence**
- Strong authorization middleware by role/ownership is explicitly listed as remaining work. fileciteturn2file1L14-L15
- The working context contains clear ownership rules, which means authorization logic will need to reflect them consistently. fileciteturn2file2L17-L24

**What needs to change**
- Implement centralized policy-based authorization.
- Enforce access based on role, object ownership, and campaign participation rules.
- Test protected endpoints and forbidden access paths.

**Priority**
Critical

---

### 1.3 Background job capability is incomplete
**Gap**
The app does not yet appear to have the asynchronous job layer needed for recalculation, reminders, and operational automation.

**Why it matters**
- Operational systems often depend on scheduled and event-driven background actions.
- Timeline recalculation, reminders, risk notifications, and workflow dependency updates are poor fits for synchronous request handling.
- Manual recovery burden rises quickly without this layer.

**Evidence**
- Workflow DAG persistence/recalculation jobs remain unfinished. fileciteturn2file1L15-L16
- Notification/reminder jobs also remain unfinished. fileciteturn2file1L16-L16
- Staging/production topology includes Redis, which suggests intended future background processing support. fileciteturn2file0L3-L4

**What needs to change**
- Add a formal background job system.
- Separate synchronous API actions from queued recalculation and notification work.
- Add retry, idempotency, and visibility for failed jobs.

**Priority**
Critical

---

## 2. High-priority gaps
These are not always immediate blockers, but they create significant delivery and support risk.

### 2.1 Test coverage is too light for a rules-heavy system
**Gap**
The visible project materials suggest a system with significant business complexity, but not yet the matching level of automated test coverage.

**Why it matters**
- Campaign generation, working-day logic, approvals, health rules, and publish readiness are all error-prone areas.
- Without strong test coverage, every schema or rules change becomes riskier.
- The more domain-driven the app becomes, the more it needs regression protection.

**Evidence**
- The implemented feature set already includes readiness gating, dual approval, risk channels, a capacity ledger, and calendar logic. fileciteturn2file1L3-L10
- The working context also locks in timeline and health rules that should be formally testable. fileciteturn2file2L6-L16

**What needs to change**
- Add unit tests around campaign generation and rule enforcement.
- Add integration tests for key endpoints and approval flows.
- Add regression tests for calendar calculations and publish-step reconciliation.

**Priority**
High

---

### 2.2 Frontend/UI is not yet mature enough for dependable internal production use
**Gap**
The backend appears ahead of the user-facing application layer.

**Why it matters**
- Even if backend rules are sound, operational adoption depends on clear, efficient UI workflows.
- Weak UI structure leads to workarounds, training burden, and inconsistent usage.
- It also increases the risk of frontend rewrites later.

**Evidence**
- Rich dashboard endpoints and frontend UI are explicitly listed as remaining work. fileciteturn2file1L16-L17
- The API examples show core lifecycle actions, but the supporting docs still frame the interface layer as incomplete. fileciteturn2file3L1-L37

**What needs to change**
- Define the long-term frontend architecture.
- Build production-quality forms, tables, filtering, permissions-aware views, and error states.
- Ensure the UI reflects operational concepts consistently.

**Priority**
High

---

### 2.3 MySQL production hardening is not complete
**Gap**
The app targets MySQL 8 in real deployments, but the final production hardening work for that database layer is not yet complete.

**Why it matters**
- Local smoke testing on SQLite is useful, but MySQL behaviour is what matters in production.
- Query performance, indexing, lock behaviour, and migration safety need validation on the target database.
- Production issues often appear only once real concurrency and real data volume are present.

**Evidence**
- MySQL 8 is the stated primary target. fileciteturn2file0L10-L10
- SQLite is explicitly positioned as local smoke-test support only. fileciteturn2file0L11-L11
- MySQL-specific indexing strategy is still listed as remaining work. fileciteturn2file1L17-L18

**What needs to change**
- Define and apply indexing for real query patterns.
- Load-test key workflows on MySQL.
- Validate transaction and concurrency behaviour for approvals and campaign generation.

**Priority**
High

---

## 3. Medium-priority gaps
These may not block a controlled first release, but they will reduce reliability or increase maintenance burden.

### 3.1 Domain terminology drift across project materials
**Gap**
There is some mismatch in naming across documents.

**Why it matters**
- Shared language matters in an operations system.
- Terminology drift eventually leaks into UI labels, APIs, analytics, and training materials.
- It becomes harder to reason about reporting and permissions when core concepts are not described consistently.

**Evidence**
- Implementation notes describe `Deal -> Campaign -> Sprint -> Module -> Deliverable -> Workflow Step`. fileciteturn2file1L3-L10
- Working context uses `Scope -> Campaign -> Stage -> Step` and states stages are first-class objects. fileciteturn2file2L4-L5

**What needs to change**
- Lock canonical vocabulary.
- Align docs, database naming, API terminology, and UI labels.
- Document any deliberate distinction between planning and execution models.

**Priority**
Medium

---

### 3.2 Operational observability is not yet clearly defined
**Gap**
The available materials do not yet show a strong operational view of logging, metrics, error monitoring, auditability, or alerting.

**Why it matters**
- Production systems need traceability when approvals, generation flows, or readiness checks fail.
- Without structured observability, support becomes reactive and slow.
- Audit visibility is particularly important in process-heavy systems.

**What needs to change**
- Add structured logs for lifecycle transitions.
- Capture audit trails for approvals, state changes, and recalculation outcomes.
- Add metrics and alerting for job failures, API errors, and latency.

**Priority**
Medium

---

### 3.3 Backup and restore process is documented but not yet proven
**Gap**
The deployment model includes backup and restore guidance, but there is no evidence here that restore operations are already part of a practiced release discipline.

**Why it matters**
- Backups are only useful if restoration is proven.
- Operational trust increases when restore testing is real, repeatable, and owned.

**Evidence**
- The deployment model specifies nightly backups, PITR, and quarterly restore simulation. fileciteturn2file0L14-L17

**What needs to change**
- Create and test restore runbooks.
- Validate RTO/RPO against realistic failure scenarios.
- Include restore drills in staging operations.

**Priority**
Medium

---

## 4. Lower-priority but important gaps
These will matter more as the app becomes widely used.

### 4.1 Configuration portability needs cleanup
**Gap**
The app still appears to have some prototype-era configuration assumptions.

**Why it matters**
- Environment drift and hidden local dependencies make support harder.
- Portable setup matters for onboarding and reliable staging parity.

**Evidence**
- The deployment model intends environment-variable-based config and secret-managed staging/production secrets. fileciteturn2file0L6-L8
- The repo analysis also identified machine-specific setup assumptions outside those docs.

**What needs to change**
- Eliminate local-machine paths and non-portable defaults.
- Ensure all operational config comes from env vars, seeded records, or admin-managed settings.

**Priority**
Lower

---

### 4.2 Dashboard and reporting layer is still incomplete
**Gap**
The system has strong domain foundations, but its management and reporting layer is still catching up.

**Why it matters**
- Operational leaders will judge the app partly by visibility, not just by data capture.
- Weak dashboards push teams back into spreadsheets and manual status tracking.

**Evidence**
- Rich dashboard endpoints are still listed as remaining work. fileciteturn2file1L16-L17

**What needs to change**
- Build operational dashboards around capacity, health, risk, approvals, and publish readiness.
- Align dashboard metrics with the locked health and status rules. fileciteturn2file2L11-L16

**Priority**
Lower

---

## Recommended go-live checklist

Before calling the app production-ready, I would expect these to be true:

- Formal migrations exist and are used in every environment.
- Authorization is centralized, enforced, and tested.
- Background jobs handle recalculation and reminders reliably.
- Key business rules have automated test coverage.
- MySQL indexing and performance are validated in staging.
- Logging, auditability, and error monitoring are in place.
- Backup and restore processes have been rehearsed.
- The frontend supports real operational use without depending on demo-only flows.

---

## Bottom line

The app looks much closer to **business-readiness** than **production-readiness**.

That is a useful stage to be at. It means the core operating model is already taking shape. But the next phase should focus less on inventing more workflow rules and more on the engineering controls that make the system safe, supportable, and durable in real use.

