# Data stewardship operations (design notes)

## Goals

Define a lightweight tenant-scoped stewardship model so governance users can triage, review, and resolve metadata/data quality actions without introducing a separate workflow engine.

## Scope

* In scope:
  * Stewardship work items generated from existing EDMP domains (quality, contracts, retention, glossary, master data).
  * Assignment, status tracking, due dates, and resolution metadata.
  * Event conventions for work item lifecycle updates.
* Out of scope (for this increment):
  * External ticketing-system synchronization.
  * Cross-tenant stewardship queues.

## Stewardship work item model (logical)

* `item_id`: UUID
* `item_type`: `quality_exception | contract_violation | retention_hold | glossary_review | mdm_merge_review`
* `subject_ref`: stable reference to the related entity (`asset_id`, `rule_id`, `term_id`, etc.)
* `severity`: `low | medium | high | critical`
* `status`: `open | in_review | blocked | resolved | dismissed`
* `assignee`: optional user/group identifier
* `due_at`: optional SLA timestamp
* `resolution`: optional structured resolution payload

## Lifecycle conventions

1. Domain components emit stewardship candidates when checks or approvals require human review.
2. Items enter `open` status with tenant and correlation context captured from request/task metadata.
3. Authorized stewards (`policy.admin` or tenant admins) can claim/reassign and transition item status.
4. Resolution updates are append-only from an audit perspective and emit events for downstream notifications.

## API and eventing direction

* API (future):
  * `POST /api/v1/stewardship/items`
  * `GET /api/v1/stewardship/items?status=open&severity=high`
  * `POST /api/v1/stewardship/items/<item_id>/transition`
* Events:
  * `stewardship.item.created`
  * `stewardship.item.assigned`
  * `stewardship.item.transitioned`
  * `stewardship.item.resolved`

## Implemented scaffold slice

* API surface:
  * `POST/GET /api/v1/stewardship/items`
  * `POST /api/v1/stewardship/items/{item_id}/transition`
* Implemented item types:
  * `quality_exception | contract_violation | retention_hold | glossary_review | mdm_merge_review`
* Implemented lifecycle statuses:
  * `open | in_review | blocked | resolved | dismissed`
* Transition actions:
  * `assign`, `start_review`, `block`, `resolve`, `dismiss`, `reopen`
* Role gates:
  * create: `catalog.editor | policy.admin | tenant.admin`
  * transition: `policy.admin | tenant.admin`
* Event and audit conventions:
  * `stewardship.item.created`
  * `stewardship.item.assigned`
  * `stewardship.item.transitioned`
  * `stewardship.item.resolved`
