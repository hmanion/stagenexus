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

## Notes for future updates
- Update this file whenever a new rule is locked or changed.
- Keep entries short and operational (decision + effect), not narrative.
