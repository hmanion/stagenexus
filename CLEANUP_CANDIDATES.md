# Cleanup Candidates After Baseline v1

## Transitional table candidate
- `sprints` (legacy demand sprint identity shape)

## Transitional column candidates
- `deliverables.sprint_id`
- `workflow_steps.sprint_id`
- `milestones.sprint_id`
- `product_modules.sprint_id`

## Compatibility alias candidate
- `workflow_steps.deliverable_id` (alias; canonical linkage is `workflow_steps.linked_deliverable_id`)

## Transitional runtime-logic candidates
- `app/db/schema_updates.py` compatibility rebuild/backfill branches that should be replaced by controlled Alembic follow-up migrations:
  - workflow step parent/linkage reshape helpers
  - sprint-to-campaign backfills
  - compatibility index creation branches
