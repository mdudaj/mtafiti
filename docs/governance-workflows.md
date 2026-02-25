# Governance workflow design notes

This note defines a governance-depth increment for EDMP focused on policy lifecycle workflows and stronger classification controls.

## Goals

* Add a tenant-scoped policy lifecycle with explicit review, approve, and rollback states.
* Keep classification controls enforceable in both API handlers and background tasks.
* Reuse existing identity, policy, and audit design conventions without introducing new external systems.

## Policy lifecycle model

Use a small state machine per tenant policy:

`draft` → `in_review` → `approved` → `active` → `superseded` | `rolled_back`

Initial rules:

* Only `policy.admin` (or `tenant.admin`) can move policies to `in_review`, `approved`, and `active`.
* Every transition records actor id, timestamp, and optional reason.
* Rollback always points to a previously `active` policy version.

## Classification controls

Define a controlled baseline vocabulary:

* `public`
* `internal`
* `confidential`
* `restricted`

Initial enforcement:

* Reject asset writes with unknown classification values.
* Require `policy.admin` for mutations that upgrade sensitivity (`internal` → `confidential`, etc.).
* Apply the same checks in worker entrypoints for async mutations.

## Audit alignment

Emit audit events for lifecycle and classification-control actions:

* `policy.submitted_for_review`
* `policy.approved`
* `policy.activated`
* `policy.rolled_back`
* `asset.classification.changed`

Event payloads should follow `docs/events.md` and `docs/audit.md` conventions.

## Non-goals (this increment)

* External policy engines or policy authoring UI.
* Cross-tenant/global workflow orchestration.
* Full legal/compliance retention workflows.
