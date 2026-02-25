# Data classification taxonomy (design notes)

This document defines a lightweight tenant-scoped data-classification model so EDMP can consistently label assets, policies, and stewardship workflows.

## Goals

* Keep classifications tenant-scoped and easy to apply to existing catalog assets.
* Provide a common vocabulary used by policy checks, retention rules, and stewardship queues.
* Reuse existing governance and eventing conventions without adding a new runtime service.

## Classification model

Suggested minimal fields:

* `classification_id`: UUID
* `name`: unique per tenant
* `level`: coarse sensitivity level (`public | internal | confidential | restricted`)
* `description`: short guidance on handling requirements
* `tags`: optional normalized labels for routing and reporting
* `status`: `draft | active | deprecated`

## Lifecycle

* Draft: created by governance owners for review.
* Activation: requires approval by `policy.admin` or `tenant.admin`.
* Active operations:
  * catalog assets may reference one or more active classifications
  * policy and retention checks consume classification level as an input signal
  * stewardship queues prioritize findings by classification sensitivity
* Deprecation: remains readable for historical audit context, but is blocked for new assignments.

## API and events (incremental direction)

Candidate endpoints:

* `POST /api/v1/classifications`
* `GET /api/v1/classifications/<id>`
* `GET /api/v1/classifications`

Candidate events:

* `classification.created`
* `classification.activated`
* `classification.deprecated`

Use the existing event envelope and tenant-scoped routing conventions from `docs/events.md`.
