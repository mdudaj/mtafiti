# Governance & policy design notes

This document captures design notes for governance capabilities (authorization, classification, audit) that build on the current multi-tenant scaffold.

## Governance building blocks

### Roles (RBAC)

Recommended initial roles (see also `docs/identity.md`):

* `catalog.reader`
* `catalog.editor`
* `tenant.admin`
* `policy.admin` (future)

### Classification & tags (metadata plane)

Extend `DataAsset` incrementally:

* `tags`: free-form labels (strings)
* `classification`: a small controlled vocabulary (e.g. `public`, `internal`, `confidential`, `restricted`)
* `owner`: string or structured object (future)

### Audit events

Every mutating action should emit an audit event (via the existing eventing envelope):

* `tenant.created`
* `asset.created`
* `asset.updated`
* `asset.deleted` (when implemented)

Audit payload (suggested minimal fields):

* `actor.user_id`
* `action` (event name)
* `resource.type` and `resource.id`
* `changes` (optional; key-level changes for JSON fields)

## Policy enforcement (later)

Policy enforcement should be introduced only after identity is in place. Start with:

* API-level checks for read/write operations
* Task-level checks for background work (Celery) using the same tenant-aware request context

## Repository workflow governance

Repository-level merge controls such as branch protection and required CI checks are operational policy, not informal maintainer preference. The maintainer runbook in `docs/operations-runbooks.md` and the helper in `.github/scripts/configure_branch_protection.py` define the auditable way to apply those controls.
