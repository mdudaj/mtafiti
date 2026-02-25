# Data access request workflow (design notes)

## Goals

Define a lightweight tenant-scoped workflow for requesting, approving, and auditing access to governed data assets without introducing an external workflow engine.

## Scope

* In scope:
  * Access-request intake for cataloged assets and data products.
  * Approval decisions by data owners/stewards with policy-aware checks.
  * Audit/event conventions for request lifecycle transitions.
* Out of scope (for this increment):
  * Integration with external IAM ticketing systems.
  * Cross-tenant approval routing.

## Access request model (logical)

* `request_id`: UUID
* `subject_ref`: stable reference to requested asset/product
* `requester`: user/service principal identifier
* `access_type`: `read | write | admin | export`
* `justification`: free-text business reason
* `status`: `submitted | in_review | approved | denied | expired | revoked`
* `approver`: optional owner/steward identifier
* `expires_at`: optional expiration timestamp

## Lifecycle conventions

1. Request is submitted with tenant, user, and correlation context.
2. Policy pre-checks validate that requested access type is eligible for approval.
3. Authorized approvers review and transition status (`approved` or `denied`).
4. Approved requests may include an expiry and are periodically revalidated by retention/governance routines.
5. All transitions are append-only from an audit perspective.

## API and eventing direction

* API (future):
  * `POST /api/v1/access-requests`
  * `GET /api/v1/access-requests?status=in_review`
  * `POST /api/v1/access-requests/<request_id>/decision`
* Events:
  * `access.request.submitted`
  * `access.request.approved`
  * `access.request.denied`
  * `access.request.revoked`
