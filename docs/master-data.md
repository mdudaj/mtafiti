# Master data management (design notes)

## Goals

Define tenant-scoped conventions for mastering shared business entities (for example: customer, provider, product, site) so downstream assets use a stable, governed source of truth.

## Scope

* In scope:
  * Canonical record model for mastered entities.
  * Source-to-master match/merge lifecycle.
  * Stewardship and approval checkpoints for high-risk merges.
  * Event conventions for create/update/merge/split actions.
* Out of scope (for this increment):
  * Real-time probabilistic matching engine implementation.
  * Cross-tenant entity mastering.

## Canonical entity model (logical)

* `entity_type`: tenant-defined type (`customer`, `product`, etc.).
* `master_id`: immutable tenant-scoped id for the golden record.
* `attributes`: normalized canonical attribute map with optional provenance tags.
* `survivorship_policy`: rule set used to resolve conflicting source values.
* `confidence`: optional score indicating match confidence.
* `status`: draft, active, superseded, archived.

## Lifecycle conventions

1. Source records are ingested with source system identifiers and version metadata.
2. Matching produces candidate links to existing masters plus confidence and explainability signals.
3. Survivorship rules compute canonical values; low-confidence outcomes require steward approval.
4. Approved changes create a new master version and emit a tenant-scoped event.
5. Consumers reference `master_id` + version semantics for reproducible downstream processing.

## API and eventing direction

* API (future):
  * `POST /api/v1/master-data/<entity_type>/records`
  * `GET /api/v1/master-data/<entity_type>/records/<master_id>`
  * `POST /api/v1/master-data/<entity_type>/merge-candidates/<id>/approve`
* Events:
  * `master-data.record.created`
  * `master-data.record.updated`
  * `master-data.record.merged`
  * `master-data.record.split`

