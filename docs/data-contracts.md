# Data contracts (design notes)

This document captures a lightweight data contract model for EDMP so producers and consumers can agree on schema and quality expectations per dataset.

## Goals

* Keep contracts tenant-scoped and attached to catalog assets.
* Version contracts without breaking existing ingestion entrypoints.
* Surface contract checks in ingestion and data quality workflows.

## Contract model

Suggested minimal fields:

* `contract_id`: UUID
* `asset_id`: target catalog asset UUID
* `version`: integer, monotonic per asset
* `status`: `draft | active | deprecated`
* `schema`: JSON schema-like structure (fields, types, nullability)
* `expectations`: list of quality expectations (required fields, ranges, uniqueness)
* `owners`: list of responsible users/groups

## Lifecycle

* Draft: editable by `catalog.editor` and `policy.admin`.
* Activation: requires governance approval (future workflow integration).
* Enforcement:
  * Ingestion validates payload/schema compatibility against the active contract.
  * Quality evaluation records expectation pass/fail per run.
* Deprecation: mark old contract versions while keeping historical references for audits.

## API and events (incremental direction)

Candidate endpoints:

* `POST /api/v1/contracts`
* `GET /api/v1/contracts/<id>`
* `GET /api/v1/assets/<asset_id>/contracts`

Candidate events:

* `contract.created`
* `contract.activated`
* `contract.deprecated`
* `contract.validation_failed`

Use the existing event envelope and tenant-scoped routing conventions from `docs/events.md`.
