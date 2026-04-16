# Roles and governance

## Purpose of this document

This page describes the **responsibility and control model**.

It covers ownership, assignment pools, and approval rights. It does not define the hierarchy or workflow sequence in detail.

## Ownership rules

Locked rules currently documented:

- one owner per object
- participants are not owners
- campaign owner is the assigned CM

This means ownership should be treated as a singular accountable role, even where several contributors participate.

## Assignment pools

Assignment pools are team-based:

- AM: Sales
- CC and CCS: Editorial
- DN and MM: Marketing
- CM: Client Services

The notes also state that CCS is a campaign slot rather than a core user-app role.

## Approval rights

### Deal approval and readiness
Operations assigns the key delivery roles and verifies readiness before campaign generation.

Typical controlled inputs include:

- Head Ops approver
- CM assignment
- CC assignment

Campaign generation is blocked unless readiness passes.

### SOW change control
Mid-campaign SOW changes do not activate immediately.

Current enforced rule:

- a change becomes active only when both required approvals are approved

The documented approval pairing is Head Ops plus Head Sales.

## Governance intent

The app is aiming to model more than assignment. It is also trying to model:

- accountability
- authority to approve or reject changes
- role-based action controls
- future authorization boundaries by role and ownership

## Implementation note

The project notes still list strong authorization middleware by role and ownership as unfinished work. So this document describes the intended governance model, not a fully hardened security layer.
