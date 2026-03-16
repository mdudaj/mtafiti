# Data products (design notes)

This document captures a lightweight data product model for Mtafiti so domain teams can publish, discover, and govern reusable analytical datasets.

## Goals

* Keep products tenant-scoped and linked to existing catalog assets.
* Define ownership and operational readiness expectations without adding a new runtime component.
* Reuse existing governance, contracts, quality, and lineage conventions.

## Product model

Suggested minimal fields:

* `product_id`: UUID
* `name`: unique per tenant
* `domain`: business domain identifier (for ownership boundaries)
* `owner`: primary owning team/user
* `asset_ids`: list of backing catalog asset UUIDs
* `sla`: freshness/availability targets (metadata only in first increment)
* `status`: `draft | active | retired`

## Lifecycle

* Draft: product definition is created and linked to candidate assets.
* Activation: requires owner assignment and at least one active data contract per critical asset.
* Active operations:
  * quality and contract checks are evaluated on ingestion updates
  * lineage reflects upstream/downstream dependencies for impact analysis
* Retirement: product remains discoverable for historical context but is excluded from new onboarding flows.

## API and events (incremental direction)

Candidate endpoints:

* `POST /api/v1/data-products`
* `GET /api/v1/data-products/<id>`
* `GET /api/v1/data-products`

Candidate events:

* `data_product.created`
* `data_product.activated`
* `data_product.retired`

Use the existing event envelope and tenant-scoped routing conventions from `docs/events.md`.

## Implemented scaffold baseline

Current scaffold implementation includes:

* `GET/POST /api/v1/data-products`
* `GET /api/v1/data-products/<product_id>`
* `POST /api/v1/data-products/<product_id>/activate`
* `POST /api/v1/data-products/<product_id>/retire`

Behavior implemented:

* tenant-scoped data product metadata (`name`, `domain`, `owner`, `asset_ids`, `sla`, `status`)
* activation guardrails:
  * owner is required
  * at least one asset is required
  * each linked asset must have an active data contract before activation
* lifecycle states `draft|active|retired`
* data product events and audit events:
  * `data_product.created`
  * `data_product.activated`
  * `data_product.retired`
