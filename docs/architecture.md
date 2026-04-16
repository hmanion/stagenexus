# Architecture

## Overview

StageNexus is a backend-first campaign operations application. The repository is structured around a separation between transport, business logic, persistence, and workflow concerns.

A useful way to understand the system is to treat it as four related but distinct layers:

1. **Domain structure** — the objects the app stores and relates
2. **Operational workflow** — the sequence in which work progresses
3. **Governance** — who owns, approves, or can act
4. **Planning rules** — how time, health, capacity, and readiness are calculated

Earlier wording around a single "structured operating model" tended to blur those together. The application is easier to reason about when they are kept separate.

## Top-level repository structure

```text
.codex/
app/
docs/
scripts/
tests/
.env.example
requirements.txt
README.md
```

## Application package structure

```text
app/
  api/
  core/
  db/
  models/
  schemas/
  seeds/
  services/
  static/
  ui/
  workflows/
  main.py
```

## Layer responsibilities

### `app/main.py`
Bootstraps the FastAPI application, mounts routes and UI, and performs startup checks.

### `app/api`
Contains route handlers. These should stay thin and delegate domain logic to services.

### `app/services`
This is the core of the application. Business rules live here, including timeline, health, capacity, readiness, campaign generation, and workflow orchestration.

Representative service areas include:

- calendar and timeline services
- campaign generation and health services
- deliverable workflow services
- change control and SOW approval services
- risk and escalation services
- capacity and override services
- work queue and operational job services

### `app/models`
SQLAlchemy models representing operational entities and supporting records such as approvals, comments, risks, audits, and capacity ledgers.

### `app/schemas`
Pydantic request and response contracts used by the API.

### `app/db`
Database configuration and runtime schema support. The current project notes indicate local schema reset support for rapid iteration.

### `app/ui` and `app/static`
A lightweight demo interface and static assets for local testing and operational visibility.

### `app/workflows`
Workflow definitions and related structures used to generate or manage execution steps.

## Architectural characteristics

### Backend-first implementation
The system is primarily an operational backend with a thin UI layer. The route surface is already substantial, which makes the backend the main product asset at this stage.

### Service-oriented domain logic
The repository already appears to keep substantial rule logic out of the route handlers. This is the right direction because it improves testability and makes later framework shifts less painful.

### Framework-agnostic domain intent
The repository notes state that the implementation is currently Python because the environment lacked Laravel tooling, but the domain and architecture are intended to remain portable.

### Time-aware operational planning
Timeline computation is a first-class concern. The application does not treat dates as generic calendar dates; it applies working-day rules, holidays, and campaign-generation defaults.

## Design boundaries

### Domain structure
The structural model should answer only:

- what objects exist
- how they relate
- which objects are parents or children

For StageNexus, the clearest current expression is:

`Deal -> Campaign -> Stage -> Step`

Deliverables sit under campaigns and can be linked to steps.

### Workflow
The workflow model should answer only:

- what happens first
- what gates later actions
- what approval flows change state

Examples include deal submission, ops approval, readiness checks, campaign generation, publish readiness, and SOW change control.

### Governance
The governance model should answer only:

- who owns each object
- who can approve changes
- which roles belong to which assignment pools

### Planning rules
The planning model should answer only:

- how dates are calculated
- what counts as a working day
- how health rolls up
- how capacity and risk are surfaced

## Key design decisions reflected in the codebase

- the structural hierarchy is explicit rather than implied
- stages are first-class planning objects
- deliverables are campaign children and can be linked to steps
- readiness is an enforced gate, not just an advisory status
- risk and capacity are system components, not reporting add-ons
- change control is approval-driven and auditable

## Current architectural gaps

The project notes identify several areas still to be strengthened:

- stronger authorisation middleware by role and ownership
- full persistence for workflow dependency DAGs
- recalculation jobs and reminders or notifications
- richer dashboard endpoints and frontend UI
- formal Alembic migration history and MySQL-specific indexing strategy
