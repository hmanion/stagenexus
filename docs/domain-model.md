# Domain model

## Purpose of this document

This page describes the **structural data model only**.

It does not try to describe the lifecycle workflow, approval rights, or planning rules in detail. Those are covered separately in:

- `workflows.md`
- `roles-and-governance.md`
- `planning-rules.md`

## Canonical structure

The clearest current structural model is:

`Deal -> Campaign -> Stage -> Step`

Deliverables are campaign children that can be linked to steps, but they are not the parent of steps.

This is the cleanest way to reconcile the repo notes that sometimes use terms such as sprint or module. Where older notes use `Sprint` or `Module`, treat those as implementation-era planning terms unless the codebase later re-establishes them as distinct first-class entities.

## Core entities

### Deal
The commercial and operational setup object.

Typical responsibilities:

- captures client and agreement details
- records campaign objective and positioning
- stores product lines and operating inputs
- moves through submission and ops approval
- acts as the parent source for campaign generation

A deal must pass the readiness gate before campaigns can be generated.

### Campaign
A delivery container generated from a deal.

Typical responsibilities:

- groups the operational work for a specific campaign instance
- pins to a template version at generation time
- carries ownership, timeline, status, and health
- acts as the parent for stages, deliverables, risks, and change control

Campaign owner is the assigned CM.

### Stage
A first-class planning and tracking segment inside the campaign.

Typical responsibilities:

- breaks campaign delivery into operational chunks
- carries timing, status, and health
- serves as the main unit for campaign health rollup
- contains execution steps

Guardrail: if any stage is Off Track, the campaign cannot be On Track.

### Step
The atomic unit of execution.

Typical responsibilities:

- carries due dates, completion state, and ownership
- links to deliverables where relevant
- supports overrides, completion, and history tracking
- is used to model detailed operational sequencing

Additional scheduling fields:

- `earliest_start_date` (dependency/window earliest feasible start)
- `planned_work_date` (primary capacity planning date)
- `completion_date` (editable completion date projection)

### Deliverable
A concrete output item associated with a campaign.

Examples may include editorial pieces, reports, interviews, or promotional assets.

Rules:

- each deliverable must map to one publication
- deliverables can move through workflow states
- deliverables support `ready_to_publish` state changes with actor tracking
- deliverables may be linked to one or more steps
- deliverables have per-campaign, per-type sequence numbering (for title generation)
- deliverables expose derived operational stage status from the most active linked stage

### Milestone
Stage-linked checkpoint entity inside campaigns.

Milestone carries:

- `name`
- `stage_id`
- `owner_user_id`
- `due_date`
- `completion_date`
- `sla_health` (`met`, `missed`, `not_due`)
- manual SLA override metadata (restricted to superadmin)
- `offset_days_from_campaign_start` for date re-anchoring when campaign start moves

## Supporting entity groups

The repository and notes indicate additional domain families such as:

- users, roles, teams, and assignments
- publications
- reviews and review windows
- benchmarks and performance tracking
- risks and escalations
- SOW change requests and approvals
- comments, notes, and audit or activity logs
- capacity ledgers and overrides

## Relationship summary

### Parent-child relationships

- a deal generates one or more campaigns
- a campaign contains stages
- a campaign contains deliverables
- a stage contains steps
- a step may be linked to a deliverable

### Important non-relationships

- deliverables are not parents of steps
- participants are not owners
- workflow sequence should not be inferred only from hierarchy

## Structural modelling guidance

When adding new entities or fields, keep these boundaries clear:

- add to the **domain model** when you are defining an object or relationship
- add to **workflow docs** when you are defining sequence or transitions
- add to **governance docs** when you are defining ownership or approval rights
- add to **planning rules** when you are defining dates, health, risk, or capacity logic
