# Business glossary (design notes)

This document captures a lightweight business glossary model for EDMP so teams can define shared business terms and map them to technical assets.

## Goals

* Keep glossary terms tenant-scoped and governed by existing role patterns.
* Link business terms to catalog assets and classifications without introducing a separate runtime.
* Support versioned term definitions with clear ownership and approval status.

## Glossary term model

Suggested minimal fields:

* `term_id`: UUID
* `name`: unique string per tenant
* `definition`: markdown/plain text definition
* `status`: `draft | approved | deprecated`
* `owners`: list of responsible users/groups
* `stewards`: list of governance users/groups
* `related_asset_ids`: optional list of `DataAsset` UUIDs
* `classifications`: optional list aligned with policy vocabulary

## Lifecycle

* Draft: editable by `catalog.editor`.
* Approval: reviewed by `tenant.admin` or `policy.admin` (future workflow integration).
* Published/approved: available to search and API consumers as canonical tenant terms.
* Deprecation: term remains queryable for history but cannot be attached to new assets.

## API and events (incremental direction)

Candidate endpoints:

* `POST /api/v1/glossary/terms`
* `GET /api/v1/glossary/terms/<id>`
* `GET /api/v1/glossary/terms?status=approved`
* `POST /api/v1/assets/<asset_id>/terms/<term_id>`

Candidate events:

* `glossary.term.created`
* `glossary.term.approved`
* `glossary.term.deprecated`
* `glossary.term.linked_to_asset`

Use the existing event envelope and tenant-scoped routing conventions from `docs/events.md`.
