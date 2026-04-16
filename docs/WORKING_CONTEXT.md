# Working Context (Ops App)
Purpose: keep a compact, up-to-date decision log so implementation stays consistent and we reduce repeated context in chat.

## Core model
- Hierarchy: Scope -> Campaign -> Stage -> Step.
- Deliverables are campaign children and can be linked to steps, but are not step parents.
- Stages are first-class objects.

## Calendar and timeline
- Working week: Mon-Thu.
- England/Wales holidays from GOV.UK.
- No weekend end/due dates.
- Demand Create/Reach generated as four campaign sprints (~90-day spacing).
- Demand Capture generated as separate annual campaign.

## Status and health
- Global status options:
  - Not started, In Progress, On Hold, Blocked: Client, Blocked: Internal, Blocked: Dependency, Done, Cancelled.
- Global health options:
  - Not due, On Track, At Risk, Off Track.
- Campaign health guardrail:
  - If any stage is Off Track, campaign cannot be On Track.

## Ownership and assignment
- One owner per object.
- Campaign owner is assigned CM.
- Participants are not owners.
- Assignment pools by team:
  - AM: Sales
  - CC/CCS: Editorial (CCS is campaign slot, not user app role)
  - DN/MM: Marketing
  - CM: Client Services

## Recent locked fixes
- Removed unsupported fallback step: "Promotion coordination".
- Per-content publish-step dedupe now uses (name + linked_deliverable_id), so two-article campaigns generate two article publish steps.
- Legacy generic publish rows are cleaned when per-content rows are reconciled.

## Newly locked rules (implementation)
- Milestones are first-class stage-linked checkpoints with owner, due date, completion date, SLA health, and campaign-start offset.
- Milestone SLA health is derived from due/completion only (`met`, `missed`, `not_due`); only superadmin can manually override SLA health.
- Milestones do not move from step dependency changes; they re-anchor when campaign start date changes.
- Parent status defaults to derived with explicit source metadata (`derived` vs `manual`); descendant changes reset parents back to derived.
- Step scheduling now includes `earliest_start_date`, `planned_work_date`, and editable `completion_date`.
- Capacity uses `planned_work_date` as primary scheduling signal; team weekly aggregates are exposed.
- Deliverable naming auto-numbers per campaign per type (for example `Article 1`, `Article 2`, `Video 1`).
- Deliverables expose derived operational status from most-active stage based on in-progress linked steps, with `not_started` fallback.

## Notes for future updates
- Update this file whenever a new rule is locked or changed.
- Keep entries short and operational (decision + effect), not narrative.
