# Data sharing (design notes)

This note captures a lightweight tenant-scoped data sharing model for EDMP so teams can publish governed shares to approved internal or external consumers.

## Goals

* Keep sharing decisions policy-driven and auditable.
* Reuse existing catalog, contracts, privacy, residency, and access-request conventions.
* Support revocation and expiry without introducing a separate data-plane runtime.

## Share model

Suggested minimal fields:

* `share_id`: UUID
* `asset_id`: referenced catalog asset UUID
* `provider_tenant`: source tenant identifier
* `consumer_ref`: approved consumer identifier (tenant, partner, or account)
* `purpose`: business/legal purpose code
* `constraints`: optional policy bundle (`masking_profile`, `row_filters`, `allowed_regions`)
* `status`: `draft | approved | active | revoked | expired`
* `expires_at`: optional timestamp

## Lifecycle conventions

1. Share is created in `draft` and linked to one or more approved access requests.
2. Approval validates policy, privacy, and residency constraints before activation.
3. Active shares are continuously evaluated against contract and retention changes.
4. Revocation/expiry immediately blocks new access grants and emits downstream events.

## API and event direction (incremental)

Candidate endpoints:

* `POST /api/v1/data-shares`
* `GET /api/v1/data-shares/<id>`
* `POST /api/v1/data-shares/<id>/revoke`

Candidate events:

* `data_share.created`
* `data_share.approved`
* `data_share.activated`
* `data_share.revoked`

Use the existing event envelope and tenant-scoped routing conventions from `docs/events.md`.

## Implemented scaffold baseline

Current scaffold implementation includes:

* `GET/POST /api/v1/data-shares`
* `GET /api/v1/data-shares/<share_id>`
* `POST /api/v1/data-shares/<share_id>/transition` with actions:
  * `approve`
  * `activate`
  * `revoke`

Behavior implemented:

* tenant-scoped data share metadata (`asset_id`, `consumer_ref`, `purpose`, `constraints`, `linked_access_request_ids`, `expires_at`, `status`)
* lifecycle states `draft|approved|active|revoked|expired`
* automatic expiry materialization when expired shares are read/listed
* constraint validation for `masking_profile`, `row_filters`, and `allowed_regions`
* data sharing events and audit events:
  * `data_share.created`
  * `data_share.approved`
  * `data_share.activated`
  * `data_share.revoked`
