# StageNexus Code Review Scorecard

## Overall verdict
A credible internal operations app scaffold with strong domain thinking and useful business-rule enforcement, but not yet at production-readiness. The backend model and service design show clear understanding of campaign operations. The main gaps are migration discipline, authorization, frontend maturity, background processing, and test depth.

**Overall score: 6.9 / 10**

---

## Scorecard

| Area | Score | What is working | Main concerns |
|---|---:|---|---|
| Product/domain modelling | 9/10 | Strong operational hierarchy, meaningful workflow concepts, readiness gating, version pinning, separate risk channels, capacity model | Some terminology drift between docs may create confusion later |
| Business rules and logic | 8.5/10 | Important constraints are encoded in the app, not left to manual process | Needs more automated validation coverage and clearer separation from route layer |
| Backend architecture | 7/10 | FastAPI + service-oriented structure is a sensible base for an internal system | Route layer looks too large and tightly coupled; likely difficult to maintain as scope grows |
| Data model / persistence | 8/10 | Rich domain model that reflects real operations rather than simplistic CRUD | Runtime schema repair is a temporary tactic, not a durable production approach |
| Database migration discipline | 4/10 | Local setup is easy and pragmatic for prototyping | Missing proper migration history; destructive reset and startup schema mutation are major risks |
| Configuration and portability | 4.5/10 | Environment-based config exists and deployment intent is documented | Hardcoded local file paths and local-machine assumptions reduce portability |
| Frontend / UI maturity | 4.5/10 | Demo UI exists and is useful for proving flow direction | Current UI appears more like a prototype shell than a maintainable application frontend |
| Security / authorization | 3.5/10 | The repo acknowledges the need for role and ownership controls | Strong authorization middleware is still a stated gap, which is a major production blocker |
| Background jobs / operational automation | 4/10 | Clear awareness of future needs such as reminders and recalculation jobs | Critical asynchronous behaviour is not yet implemented |
| Testing and reliability | 4.5/10 | Some test structure exists | Visible test depth looks too light for a rules-heavy operational system |
| Deployment readiness | 6/10 | Reasonable staging/production topology is documented, with MySQL as the target | Production practices depend on migration hardening, indexing, backups being truly exercised |
| Maintainability | 6.5/10 | Good intent, strong docs, and clear business orientation | Risk of complexity build-up unless modules are split and responsibilities tightened |

---

## What the repository does well

### 1. The domain model is the strongest part of the repo
The app appears designed around how campaign operations actually behave, rather than around a generic task tracker. The hierarchy and rules around campaigns, deliverables, workflow steps, approvals, risks, and capacity suggest the author understands the working model well.

Why that matters:
- It lowers the risk of building the wrong app with a polished interface on top.
- It creates a stronger foundation for automation and reporting later.
- It is harder to retrofit this kind of domain clarity after the fact.

### 2. Core operational constraints are being enforced in code
The readiness gate before campaign generation, publication mapping requirement, and dual-approval model for SOW changes are exactly the kinds of controls that should live in the system.

Why that matters:
- It reduces process drift.
- It makes the system more trustworthy for operations teams.
- It improves future auditability.

### 3. The deployment intent is sensible
The repo distinguishes local, staging, and production environments and targets MySQL 8 for real deployments, which is the correct direction for a system like this.

---

## Main weaknesses

### 1. Migration discipline is not ready for real data
This is the single biggest engineering concern.

Symptoms:
- Destructive database reset for setup workflows.
- Runtime schema mutation/repair on app startup.
- Stated absence of a proper migration history.

Why it matters:
- It increases the chance of data integrity problems.
- It makes deployments riskier.
- It becomes difficult to reason about schema state across environments.

Recommended fix:
- Move fully to Alembic migrations.
- Stop relying on startup repair for structural changes.
- Treat SQLite as disposable local smoke-test only.

### 2. Authorization appears underdeveloped
The implementation notes explicitly identify strong authorization middleware by role/ownership as unfinished.

Why it matters:
- This is not a minor enhancement; it is a core production requirement.
- Operational systems often contain commercially sensitive timelines, ownership, and client information.
- Weak authorization becomes harder to fix once API sprawl grows.

Recommended fix:
- Introduce a central policy layer for role, ownership, and campaign-level access.
- Keep route handlers thin and avoid one-off authorization checks.

### 3. The route layer likely carries too much responsibility
The API route file appears to import a wide span of models, schemas, and services, which usually signals an orchestration bottleneck.

Why it matters:
- Harder testing.
- Harder refactoring.
- Higher risk of business rules becoming duplicated or inconsistently enforced.

Recommended fix:
- Split routes by bounded context.
- Push orchestration into application services.
- Keep route handlers focused on transport concerns only.

### 4. The UI is not yet a robust application layer
The current UI looks sufficient for demoing paths and screens, but not yet for a maintainable internal product.

Likely implications:
- Limited interactive depth.
- Growing complexity if server-rendered demo HTML is extended too far.
- Future rewrite risk if the frontend architecture is not decided soon.

### 5. Portability issues are still present
A hardcoded local CSV path is a practical warning sign.

Why it matters:
- It creates hidden setup dependencies.
- It makes onboarding and deployment less predictable.
- It suggests some business-critical configuration still lives outside the app lifecycle.

Recommended fix:
- Move step-hour definitions into seeded data, managed uploads, or database-backed admin settings.

---

## Production-readiness view

### Ready enough for
- Local prototyping
- Internal workflow validation
- Modelling and testing the operational design
- Early stakeholder demos

### Not ready enough for
- Broad internal adoption with real operational dependency
- Multi-user production use with meaningful data sensitivity
- Safe iterative deployment across environments
- Long-lived maintainable feature expansion without refactoring

---

## Architectural judgement

This repository is much better as an **operations engine prototype** than as a finished app.

That is not a criticism. In fact, for this kind of system, getting the domain and rules right first is usually the more difficult and more valuable part. The concern is that the codebase now needs a deliberate second phase focused on engineering hardening rather than more feature spread.

---

## Highest-priority actions

### Immediate
1. Introduce proper migration history and remove structural startup repair dependency.
2. Implement centralized authorization and ownership checks.
3. Remove machine-specific config assumptions.
4. Add tests around campaign generation, working-day logic, risk escalation, and SOW approval activation.

### Next
5. Split oversized route modules by domain area.
6. Decide the long-term frontend path and avoid expanding a throwaway UI shell into a permanent solution.
7. Add background job support for reminders, recalculation, and notifications.
8. Define MySQL indexing and performance strategy before data volume grows.

### Later
9. Improve dashboard/reporting endpoints.
10. Add stronger observability, audit logging, and restore testing around production operations.

---

## Suggested final assessment

If this were a formal review, I would describe the repo as:

> A promising and thoughtfully modelled internal operations platform with strong business-rule foundations, currently in late-prototype or early-hardening stage. Its value is already visible in the domain design, but it still needs disciplined work on migrations, authorization, testing, and frontend architecture before it should be treated as a dependable production application.

---

## One-line summary

**Good foundation, good operational thinking, not yet hardened enough to trust as a production system.**

