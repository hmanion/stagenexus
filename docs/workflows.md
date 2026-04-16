# Workflows

## Purpose of this document

This page describes the **operational lifecycle and state flows**.

It does not define the object hierarchy in detail. For structure, see `domain-model.md`.

## Main lifecycle

The main operational workflow starts with a deal and ends in active campaign execution.

`Create deal -> Submit deal -> Ops approval -> Readiness check -> Generate campaigns -> Execute campaigns`

## Deal to campaign lifecycle

### 1. Create deal
A deal is created with client, commercial dates, campaign objective, positioning, and product line information.

### 2. Submit deal
The deal is moved into a submitted state for operational review.

### 3. Ops approval and readiness check
Operations assigns the key delivery roles and checks that the deal is ready for campaign generation.

Typical role assignments during this stage include:

- Head Ops approver
- CM
- CC

Campaign generation is blocked unless readiness passes.

### 4. Generate campaigns
The app generates campaigns from the approved deal, pins the template version, and creates the relevant execution structure.

### 5. Execute campaigns
Users work through deliverables and steps, monitor risks and capacity, and manage ongoing operational status.

## Publish readiness workflow

Deliverables move through workflow states during execution. One important checkpoint is `ready_to_publish`.

The repository notes indicate:

- deliverable workflow states include `ready_to_publish`
- the endpoint tracks the acting user and acting role
- CM and CC readiness actions are explicitly supported

This makes publish readiness both operational and auditable.

## SOW change workflow

Mid-campaign SOW changes are controlled through a parallel approval model.

### Steps

1. create a change request against a campaign
2. capture requested impact, such as a timeline change
3. collect approval decisions from the required approvers
4. activate the change only after both required approvals are approved

This prevents informal scope drift from silently changing the plan.

## Risk and escalation workflow

The system supports two types of risks:

- system-generated risks
- manually logged risks

These can feed escalation handling where intervention is needed.

## Capacity workflow

The application includes a capacity ledger with warning and override behaviour.

Typical flow:

1. work allocation is evaluated against weekly capacity
2. the system records warnings where thresholds are exceeded
3. an override can be requested
4. the override is reviewed and approved or rejected

Primary scheduling signal:

- capacity now keys work to step `planned_work_date` (with temporary migration fallback to start dates)
- team weekly aggregates are exposed for manager views

## Health rollup workflow

Health is not a cosmetic field. It is constrained by stage-level conditions.

Rule:

- if any stage is Off Track, the parent campaign cannot be On Track

This means campaign health should be derived or validated from lower-level operational state.

Status override reset behaviour:

- parent status is derived by default
- manual parent override is explicit and flagged
- when descendants change, parent status resets back to derived

## Milestone workflow

- milestones are stage-linked checkpoints and do not follow step dependency auto-moves
- SLA health is computed from due date vs completion date only
- if campaign start date changes, milestone due dates re-anchor from stored start offsets
- manual SLA override is restricted to superadmin

## Example API sequence

```bash
# Create deal
curl -X POST http://localhost:8000/api/deals \
  -H "Content-Type: application/json" \
  -d '{
    "client_name":"Acme Corp",
    "am_user_id":"<am-user-id>",
    "sow_start_date":"2026-04-07",
    "sow_end_date":"2027-04-01",
    "campaign_objective":"Increase visibility",
    "messaging_positioning":"Thought leadership",
    "product_lines":[{"product_type":"demand","tier":"silver","options_json":{}}]
  }'

# Submit deal
curl -X POST http://localhost:8000/api/deals/<deal-id>/submit

# Ops approve
curl -X POST http://localhost:8000/api/deals/<deal-id>/ops-approve \
  -H "Content-Type: application/json" \
  -d '{
    "head_ops_user_id":"<ops-user-id>",
    "cm_user_id":"<cm-user-id>",
    "cc_user_id":"<cc-user-id>"
  }'

# Generate campaigns
curl -X POST http://localhost:8000/api/deals/<deal-id>/generate-campaigns
```
