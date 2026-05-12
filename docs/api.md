# API guide

## Overview

The API is mounted under `/api` and exposed through FastAPI. Swagger documentation is available locally at `/docs`.

The current route surface covers the main operational areas below.

## Health

- `GET /health`

Basic application health endpoint.

## Scopes

- `POST /api/scopes`
- `POST /api/scopes/{scope_id}/submit`
- `POST /api/scopes/{scope_id}/ops-approve`
- `POST /api/scopes/{scope_id}/generate-campaigns`

Some compatibility aliases may still exist for `/scopes` while the naming transition to `/scopes` completes.

## Campaigns

- `GET /api/campaigns`
- `GET /api/campaigns/{campaign_id}`
- `GET /api/campaigns/{campaign_id}/health`
- `GET /api/campaigns/{campaign_id}/workspace`

Fetch a campaign and its current state.

Campaign list rows include `health`, `campaign_health`, and `health_reason`. These values are assembled from the live timeline-health evaluation for the returned campaigns so list health aligns with the workspace health summary.

## Deliverables

- `POST /api/deliverables/{deliverable_id}/ready-to-publish`
- `POST /api/deliverables/{deliverable_id}/transition`
- `GET /api/deliverables/{deliverable_id}/history`

These endpoints support state transitions, publish readiness, and lifecycle visibility.

## Workflow steps

- `POST /api/workflow-steps/{step_id}/complete`
- `POST /api/workflow-steps/{step_id}/override-due`

These endpoints support execution progress and due-date control.

## SOW change control

- `POST /api/campaigns/{campaign_id}/sow-change-requests`
- `POST /api/sow-change-requests/{request_id}/decide`

These implement controlled mid-campaign scope change.

## Capacity

- `GET /api/capacity-ledger`
- `POST /api/capacity-ledger/{capacity_id}/request-override`
- `POST /api/capacity-ledger/{capacity_id}/decide-override`

These provide visibility into weekly capacity and controlled override handling.

## Risks and escalations

- `GET /api/risks/system`
- `GET /api/risks/manual`
- `POST /api/risks/manual`
- `PATCH /api/risks/manual/{risk_id}`
- `GET /api/escalations`
- `POST /api/escalations/{escalation_id}/resolve`

## Work queues and dashboards

- `GET /api/users/{user_id}/work-queue`
- `GET /api/dashboard/role`

## Operational jobs

- `POST /api/jobs/run-ops-risk-capacity`

Useful for recomputation or operational processing in development and support flows.

## Example requests

### Create scope

```bash
curl -X POST http://localhost:8000/api/scopes \
  -H "Content-Type: application/json" \
  -d '{
    "client_name":"Acme Corp",
    "am_user_id":"<am-user-id>",
    "sow_start_date":"2026-04-07",
    "sow_end_date":"2027-04-01",
    "campaign_objective":"Increase visibility",
    "messaging_positioning":"Thought leadership",
    "product_lines":[{"product_type":"demand","tier":"silver","options_json":{"demand_module_mode":"create_reach_capture"}}]
  }'
```

Valid demand module modes include:

- `create_only`
- `create_reach`
- `create_reach_capture`

### Submit scope

```bash
curl -X POST http://localhost:8000/api/scopes/<scope-id>/submit
```

### Ops approve

```bash
curl -X POST http://localhost:8000/api/scopes/<scope-id>/ops-approve \
  -H "Content-Type: application/json" \
  -d '{
    "head_ops_user_id":"<ops-user-id>",
    "cm_user_id":"<cm-user-id>",
    "cc_user_id":"<cc-user-id>"
  }'
```

### Create change request

```bash
curl -X POST http://localhost:8000/api/campaigns/<campaign-id>/sow-change-requests \
  -H "Content-Type: application/json" \
  -d '{"requested_by_user_id":"<user-id>","impact_scope_json":{"timeline":"+5 working days"}}'
```

### Mark deliverable ready to publish

```bash
curl -X POST "http://localhost:8000/api/deliverables/<deliverable-id>/ready-to-publish?actor_user_id=<id>&actor_role=cm"
```
