# Planning rules

## Purpose of this document

This page describes the rules that shape schedules, health, risk, and capacity.

These are planning and control rules, not the object hierarchy.

## Calendar rules

- working week is Monday to Thursday
- England and Wales holidays come from GOV.UK
- no weekend due or end dates

## Campaign generation defaults

- demand create/reach work is generated as four campaign sprints at roughly 90-day spacing
- `options_json.demand_module_mode` controls which modules are created for demand sprint campaigns
- `create_only` demand mode creates only the `create` module, omits reach, and does not create promotion or reporting work
- `create_reach` and `create_reach_capture` demand modes create both `create` and `reach` modules for the sprint campaigns
- `create_reach_capture` also generates demand capture as a separate annual campaign
- demand capture campaigns include only the `capture` module and lead-total deliverable, starting in production; they do not create promotion or reporting stages

These are generation rules and scheduling defaults, not structural hierarchy rules.

## Stage creation rules

- planning and production are baseline stages for campaigns
- promotion is conditional
- demand campaigns get promotion only when reach is enabled
- non-demand campaigns keep promotion when promotional deliverables or promotion-linked workflow exists
- reporting is conditional
- demand campaigns get reporting only when reach is enabled and reporting work exists
- empty optional promotion/reporting stages are removed during integrity repair, along with their stage-linked milestones

Stage/step hours used during campaign planning are reference data. The default CSV is `app/seeds/stage_steps_hours.csv`, and operators can seed DB-backed reference data with `PYTHONPATH=. python scripts/seed_reference_data.py`.

## Status values

- Not started
- In Progress
- On Hold
- Blocked: Client
- Blocked: Internal
- Blocked: Dependency
- Done
- Cancelled

## Health values

- Not due
- On Track
- At Risk
- Off Track

## Health guardrail

- if any stage is Off Track, the campaign cannot be On Track

This means campaign health should be constrained by lower-level delivery conditions.

Campaign list responses now evaluate timeline health at read time so list pills match the campaign workspace view. Stored campaign health fields remain useful for persistence and audit context, but the displayed list health should be treated as the live timeline-health result when child records are available.

## Risk rules

Risk is split into two channels:

- `risks_system`
- `risks_manual`

This allows the app to distinguish calculated operational issues from manually raised concerns.

## Capacity rules

The application includes a weekly capacity ledger with warning and override behaviour.

The intent is to surface over-allocation early rather than allowing it to remain implicit in timeline slippage.
