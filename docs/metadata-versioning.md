# Metadata versioning (design notes)

This note captures a lightweight tenant-scoped metadata versioning model for Mtafiti so asset definitions can evolve with an auditable change history.

## Goals

* Keep metadata changes traceable and reversible.
* Reuse existing catalog, glossary, and contract conventions.
* Support draft/review/publish flow without introducing a separate metadata store.

## Version model

Suggested minimal fields:

* `version_id`: UUID
* `asset_id`: referenced catalog asset UUID
* `version_number`: monotonically increasing integer
* `change_summary`: short human-readable description
* `change_set`: structured diff payload (`schema`, `ownership`, `classifications`, `terms`)
* `status`: `draft | published | superseded`
* `created_by`: user/principal identifier
* `created_at`: timestamp

## Lifecycle conventions

1. Metadata edits create a new `draft` version linked to the current published baseline.
2. Validation checks contract compatibility and required ownership/classification fields.
3. Publish marks draft as `published` and previous published version as `superseded`.
4. Rollback is implemented by publishing a new version generated from a prior baseline.

## API and event direction (incremental)

Candidate endpoints:

* `POST /api/v1/assets/<id>/versions`
* `GET /api/v1/assets/<id>/versions`
* `POST /api/v1/assets/<id>/versions/<version_id>/publish`

Candidate events:

* `asset_version.created`
* `asset_version.published`
* `asset_version.superseded`

Use the existing event envelope and tenant-scoped routing conventions from `docs/events.md`.

## Implemented scaffold baseline

Current scaffold implementation includes:

* `POST /api/v1/assets/<asset_id>/versions`
* `GET /api/v1/assets/<asset_id>/versions`
* `POST /api/v1/assets/<asset_id>/versions/<version_id>/publish`

Behavior implemented:

* tenant-scoped metadata version model (`version_number`, `change_summary`, `change_set`, `status`, `created_by`)
* lifecycle states `draft|published|superseded`
* publish validation gates:
  * owner must be present from change set or current asset metadata
  * at least one valid classification must be present
  * schema changes are blocked when incompatible with the active data contract
* publish action supersedes previously published versions for the same asset
* metadata version events and audit events:
  * `asset_version.created`
  * `asset_version.published`
  * `asset_version.superseded`
