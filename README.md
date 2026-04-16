# StageNexus

StageNexus is a campaign operations application for Today Digital. It manages campaign delivery from commercial setup through execution.

The repository currently has a strong operational backend, but some of the earlier wording around its "structured operating model" blurred together four different things:

- the **domain structure** of work objects
- the **lifecycle workflow** of a campaign
- the **roles and governance** model
- the **planning rules** that shape dates, capacity, and health

This documentation set separates those concerns so the app is easier to understand and extend.

## What the app is actually modelling

### 1. Domain structure
The core data structure is best understood as:

`Deal -> Campaign -> Stage -> Step`

Deliverables are campaign children that can be linked to steps, but they are not parents of steps.

### 2. Lifecycle workflow
The main operational flow is:

`Create deal -> Submit deal -> Ops approve -> Readiness check -> Generate campaigns -> Execute -> Publish readiness / change control`

### 3. Roles and governance
The app also models ownership, team assignment, approval rights, and action controls such as CM ownership and dual approval for SOW changes.

### 4. Planning rules
The app applies working-day logic, holiday rules, health rollups, capacity warnings, and campaign-generation defaults.

## What it currently covers

- deal creation, submission, operational approval, and campaign generation
- campaign, stage, deliverable, and step entities
- working-day timeline logic using a Monday to Thursday working week
- England and Wales holiday handling via a GOV.UK holiday source
- readiness gating before campaigns can be generated
- template version pinning during campaign generation
- deliverable workflow states, including `ready_to_publish`
- separate manual and system risk channels
- capacity warnings and override flows
- SOW change control with dual approval
- work queue, escalation, and dashboard endpoints

## Stack

- FastAPI
- SQLAlchemy 2.x
- Pydantic 2.x
- Uvicorn
- MySQL 8 as the primary target
- SQLite for local smoke testing and rapid iteration

## Quick start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --port 8000
```

Open:

- `http://127.0.0.1:8000/` for the demo UI
- `http://127.0.0.1:8000/docs` for Swagger/OpenAPI docs

To initialise local schema and seed data:

```bash
PYTHONPATH=. python scripts/init_db.py
```

To backfill existing local data to newer workflow and timeline defaults:

```bash
PYTHONPATH=. .venv/bin/python scripts/backfill_recent_updates.py
```

## Documentation set

- `docs/architecture.md` — system structure and design boundaries
- `docs/domain-model.md` — domain objects and their relationships
- `docs/workflows.md` — operational lifecycle and approval flows
- `docs/roles-and-governance.md` — ownership, assignments, and approval rights
- `docs/planning-rules.md` — calendar, health, risk, and capacity rules
- `docs/api.md` — API areas and example requests
- `docs/deployment.md` — environments, config, and deploy guidance
- `docs/roadmap-and-gaps.md` — known limitations and next implementation priorities

## Core operational rules

- working week is Monday to Thursday
- no weekend due or end dates
- England and Wales holidays come from GOV.UK
- one owner per object
- campaign owner is the assigned CM
- one deliverable maps to one publication
- campaign generation is blocked unless readiness passes
- mid-campaign SOW changes only activate after both required approvals are approved
- if any stage is Off Track, the campaign cannot be On Track

## Suggested next repository cleanup

- replace the current root README with this version or merge the key sections into it
- move project notes from ad hoc files into the `docs/` folder in the repo
- align remaining repo language around `Deal -> Campaign -> Stage -> Step`
- keep workflow, governance, and planning rules in separate docs rather than merging them into one model page
- add an endpoint inventory generated from the route layer once the API stabilises
- add migration documentation when Alembic history is formalised
