# Data residency controls (design notes)

This document defines a lightweight tenant-scoped residency model so EDMP can enforce where governed metadata and processing outputs are allowed to persist.

## Goals

* Keep residency rules tenant-scoped and explicit in metadata.
* Reuse existing policy, connector, and retention conventions instead of introducing a dedicated service.
* Provide clear allow/deny signals for ingestion, movement, and export flows.

## Residency profile model

Suggested minimal fields:

* `residency_profile_id`: UUID
* `name`: unique per tenant
* `allowed_regions`: list of region identifiers (`eu-central-1`, `us-east-1`, etc.)
* `blocked_regions`: optional explicit deny list for stricter controls
* `enforcement_mode`: `advisory | enforced`
* `status`: `draft | active | deprecated`

## Lifecycle

* Draft: governance owners define allowed/blocked region constraints.
* Activation: requires approval by `policy.admin` or `tenant.admin`.
* Active operations:
  * assets and data products may reference one active residency profile
  * connector executions validate destination region against profile constraints
  * policy checks can block exports when target region is outside allowed scope
* Deprecation: profile remains readable for audit history but is blocked for new assignments.

## API and events (incremental direction)

Candidate endpoints:

* `POST /api/v1/residency/profiles`
* `GET /api/v1/residency/profiles/<id>`
* `GET /api/v1/residency/profiles`

Candidate events:

* `residency.profile.created`
* `residency.profile.activated`
* `residency.violation.detected`

Use the existing event envelope and tenant-scoped routing conventions from `docs/events.md`.
