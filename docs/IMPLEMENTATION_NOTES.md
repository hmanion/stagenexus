# Implementation Notes

## What is implemented
- Operational hierarchy: Deal -> Campaign -> Sprint -> Module -> Deliverable -> Workflow Step.
- Operational readiness gate before campaign generation.
- Template version pinning via `template_versions` reference on campaigns.
- Deliverable workflow states including `ready_to_publish`.
- CM/CC publish readiness endpoint with actor tracking.
- Parallel dual-approval SOW change flow (Head Ops + Head Sales).
- Separate risk channels (`risks_system`, `risks_manual`).
- Capacity ledger with role weekly capacities and override metadata.
- Working-day calendar service with Mon-Thu default and UK Gov holiday source.

## Key constraints enforced
- One deliverable maps to one publication (`deliverables.publication_id` required).
- Campaign generation blocked unless readiness gate passes.
- Mid-campaign SOW changes activate only when both required approvals are approved.

## Remaining for next increment
- Strong authorization middleware by role/ownership.
- Full workflow dependency DAG persistence and recalculation jobs.
- Notification/reminder jobs.
- Rich dashboard endpoints and frontend UI.
- Alembic migration history and MySQL-specific indexing strategy.
