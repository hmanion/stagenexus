# StageNexus Migration Notes (Baseline v1)

## Purpose
This baseline introduces formal Alembic migration discipline while preserving migration-window compatibility objects needed by the running app.

## Canonical baseline schema
- Core hierarchy: `Deal -> Campaign -> Stage -> WorkflowStep`.
- Campaign child records: `deliverables`, `product_modules`, `milestones`.
- Included first-class current features: `review_windows`, `review_round_events`.
- Identity/access, commercial setup, reference/config, risk/performance/capacity/audit tables are all part of baseline v1.
- Auxiliary current-state tables retained: `public_id_counters`, `notes`.

## Transitional compatibility baggage retained intentionally
- `sprints` table remains for migration-window safety.
- Compatibility `sprint_id` links remain on:
  - `deliverables`
  - `workflow_steps`
  - `milestones`
  - `product_modules`
- `workflow_steps.deliverable_id` remains as a compatibility alias while `linked_deliverable_id` is the canonical deliverable linkage for steps.
- Runtime schema patching (`ensure_runtime_schema`) remains temporarily for rollout safety and is now explicitly marked as transitional compatibility debt.

## Long-term target state
- Campaign records persist demand sprint identity via campaign fields:
  - `is_demand_sprint`
  - `demand_sprint_number`
  - `demand_track`
  - optional grouping key (future migration decision)
- `sprints` table is legacy/transitional and a removal candidate after compatibility links are retired.
- `product_modules` remain campaign-scoped persisted records.
