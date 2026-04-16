# Planning rules

## Purpose of this document

This page describes the rules that shape schedules, health, risk, and capacity.

These are planning and control rules, not the object hierarchy.

## Calendar rules

- working week is Monday to Thursday
- England and Wales holidays come from GOV.UK
- no weekend due or end dates

## Campaign generation defaults

- demand create and demand reach are generated as four campaign sprints at roughly 90-day spacing
- demand capture is generated as a separate annual campaign

These are generation rules and scheduling defaults, not structural hierarchy rules.

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

## Risk rules

Risk is split into two channels:

- `risks_system`
- `risks_manual`

This allows the app to distinguish calculated operational issues from manually raised concerns.

## Capacity rules

The application includes a weekly capacity ledger with warning and override behaviour.

The intent is to surface over-allocation early rather than allowing it to remain implicit in timeline slippage.
