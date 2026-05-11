# Authorization Policy Matrix

## Scope

This document maps mutable and sensitive-read API endpoints to centralized authorization policy in `app/services/authz_service.py` and route usage in `app/api/routes/*` and `app/api/core_routes.py`.

## Actor resolution

- Canonical identity source is the resolved actor in `AuthzService.resolve_actor_identity(...)`.
- Transitional compatibility: endpoints that still send `payload.actor_user_id` are accepted, but identity is still resolved through `authz_service`.
- If both a route actor (for example query/header actor) and payload actor are provided and differ, only admin/superadmin may override.
- Caller-provided role strings are never trusted by themselves; effective roles are loaded from DB role assignments + derived team/seniority roles.

## Endpoint inventory by class

### Public/system health

- `GET /health`
- `GET /api/campaigns/health`

### Read-only low sensitivity

- `GET /api/publications`
- `GET /api/campaigns`
- `GET /api/deals` (`/api/scopes` alias)
- `GET /api/workflow-steps`
- `GET /api/milestones`
- `GET /api/dashboard/summary`

### Read-only sensitive

- `GET /api/users`
- `GET /api/users/{user_id}/panel`
- `GET /api/users/{user_id}/work-queue`
- `GET /api/my-work`
- `GET /api/capacity-ledger`
- `GET /api/capacity/matrix`
- `GET /api/risks/system`
- `GET /api/risks/manual`
- `GET /api/escalations`
- `GET /api/campaigns/{campaign_id}/workspace`
- `GET /api/deliverables/{deliverable_id}/history`
- `GET /api/deliverables/{deliverable_id}/review-windows`

### Mutable standard

- Deal/scope edits: AM, content, timeframe
- Campaign assignment/status/date edits
- Workflow step complete/manage
- Deliverable transition/date/stage/owner updates
- Milestone update/completion/SLA override
- Manual risk create/update

### Mutable privileged

- Campaign delete
- Deliverable delete
- Due-date override endpoints
- Admin user and role/admin-control endpoints
- Capacity override decision
- Ops job trigger

### Approval/state-transition critical

- Deal ops approval
- Campaign generation from approved deal
- SOW change request create + decision + activation
- Ready-to-publish transition
- Campaign descendant status cascade
- Escalation resolve

## Compact access matrix

Action | Allowed actors | Ownership rule | Notes
--- | --- | --- | ---
Create deal/scope | `AM`, `ADMIN` | `am_user_id` must equal actor unless admin | `POST /api/deals`
Update protected deal fields | deal owner (`am_user_id`) or `{ADMIN, HEAD_OPS, HEAD_SALES}` | Non-owner blocked | AM/content/timeframe/delete handlers
Submit deal | deal owner or `{ADMIN, HEAD_OPS}` | Owner-or-privileged | `POST /api/deals/{id}/submit`
Ops approve deal | control `approve_scope` or `{HEAD_OPS, ADMIN}` (legacy leadership fallback) | N/A | `POST /ops-approve`
Generate campaigns | control `generate_latest_campaigns` or `{HEAD_OPS, ADMIN}` (legacy leadership fallback) | Deal must be `READINESS_PASSED` | `POST /generate-campaigns`
Manage campaign assignments | control `manage_campaign_assignments` or `manage_step` fallback set | Campaign scope | Assignment pool team constraints enforced
Update campaign status/dates | control `manage_campaign_status`/`manage_campaign_dates` with fallback `{CM, HEAD_OPS, ADMIN}` | Campaign scope | Actor captured in activity log
Cascade campaign descendant status | same as campaign status | Campaign scope | explicit confirmation phrase required
Transition deliverable | assigned campaign member role `{AM, CM, CC, CCS}` or `{HEAD_OPS, ADMIN}` | Membership-based | `POST /deliverables/{id}/transition`
Mark ready to publish | assigned campaign member role `{CM, CC}` or `{HEAD_OPS, ADMIN}` | Membership-based | writes `ready_to_publish_by_user_id`
Decide SOW change | `{HEAD_OPS, HEAD_SALES, ADMIN}` and actor must hold requested approver role (unless admin) | N/A | dual-approval activation enforced in service
Request capacity override | row owner or `{CM, HEAD_OPS, ADMIN}` | Owner-preferred | `POST /capacity-ledger/{id}/request-override`
Decide capacity override | `{HEAD_OPS, ADMIN}` | N/A | actor recorded by service
Manual risk update | `{CM, HEAD_OPS, ADMIN}` | N/A | restricted mutation path
Resolve escalation | `{HEAD_OPS, ADMIN}` | N/A | sensitive state transition
Run ops job | `{HEAD_OPS, ADMIN}` | N/A | `POST /jobs/run-ops-risk-capacity`
Admin reference changes | controls under `admin_*` app controls | N/A | enforced via `has_control_permission`

## Audit-friendly actor capture

Currently captured for sensitive transitions where model fields/logging exist:

- ops approval (deal service path)
- campaign generation (activity/state path)
- publish readiness (`ready_to_publish_by_user_id`, timestamp)
- SOW decisions (`approver_user_id`, role, status)
- capacity override decisions (`actor_user_id` in service)
- manual risk updates (`raised_by_user_id` / update actor path)
- escalation resolution (`resolved_at`, actor enforced)

## Known TODOs

- Add explicit actor field on escalation resolution model if historical resolver identity needs to be queried directly without external logs.
- Standardize sensitive read endpoint gating for cross-team visibility where currently open by design.
