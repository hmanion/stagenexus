# Campaign Operations App

Purpose-built campaign operations backend for Today Digital, implementing the agreed operating model:
`Deal -> Campaign -> Sprint -> Module -> Deliverable -> Workflow Step`.

## Implemented in this scaffold
- Domain entities for deals, campaigns, sprints, modules, deliverables, workflow, reviews, risks, benchmarks, capacity, SOW changes, audit log.
- Working-day timeline engine (Mon-Thu) with England/Wales holiday support from GOV.UK.
- Risk channels separated into system and manual risks.
- Capacity ledger with warn-and-override model.
- Operational readiness gate on deals.
- Template version pinning during campaign generation.

## Quick start
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --port 8000
```

Note: `scripts/init_db.py` currently resets the local schema (drop + recreate) for rapid iteration.

Then open:
- `http://127.0.0.1:8000/` (user demo UI)
- `http://127.0.0.1:8000/docs` (API docs)

## Data backfill for recent model updates
To migrate existing deals/campaigns/sprints to the latest timeline + workflow defaults:
```bash
PYTHONPATH=. .venv/bin/python scripts/backfill_recent_updates.py
```
This normalizes legacy sprint milestones, moves legacy KO/interview deliverables into sprint workflow steps, refreshes template pinning, and recomputes risk/capacity ledgers.

## API (starter)
- `GET /health`
- `POST /api/deals`
- `POST /api/deals/{deal_id}/submit`
- `POST /api/deals/{deal_id}/ops-approve`
- `POST /api/deals/{deal_id}/generate-campaigns`
- `GET /api/campaigns/{campaign_id}`
- `GET /api/users/{user_id}/work-queue`
- `POST /api/campaigns/{campaign_id}/sow-change-requests`
- `POST /api/sow-change-requests/{request_id}/decide`
- `POST /api/deliverables/{deliverable_id}/ready-to-publish`
- `POST /api/deliverables/{deliverable_id}/transition`
- `GET /api/deliverables/{deliverable_id}/history`
- `POST /api/workflow-steps/{step_id}/complete`
- `POST /api/workflow-steps/{step_id}/override-due`
- `POST /api/jobs/run-ops-risk-capacity`
- `GET /api/capacity-ledger`
- `POST /api/capacity-ledger/{capacity_id}/request-override`
- `POST /api/capacity-ledger/{capacity_id}/decide-override`
- `GET /api/risks/system`
- `GET /api/risks/manual`
- `POST /api/risks/manual`
- `PATCH /api/risks/manual/{risk_id}`
- `GET /api/escalations`
- `POST /api/escalations/{escalation_id}/resolve`
- `GET /api/dashboard/role`

## Notes
- This environment lacked PHP/Laravel tooling; this scaffold is implemented in Python to deliver a working system backbone now.
- The architecture and domain are kept framework-agnostic so migration to Laravel 11 remains straightforward.
