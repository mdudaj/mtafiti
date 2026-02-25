# Policy enforcement design notes

This note defines a minimal policy-enforcement increment for EDMP.

## Goals

* Enforce role-based access checks consistently in tenant-scoped APIs.
* Establish a path to attribute-based policy checks without changing API shapes.
* Reuse current request context (`X-User-Id`, `X-User-Roles`, correlation id) across API and worker paths.

## Enforcement model (initial)

* Keep enforcement opt-in via `EDMP_ENFORCE_ROLES` for phased rollout.
* Require:
  * read APIs: `catalog.reader` (or stronger)
  * mutating APIs: `catalog.editor` or `tenant.admin` depending on resource type
* Return explicit authorization errors (HTTP 403) with stable machine-readable payloads.

## ABAC path (next)

Add tenant-scoped policy rules that evaluate:

* `subject`: user id, roles, groups (future OIDC claims)
* `resource`: asset type, classifications, tags, owner
* `action`: read/create/update/delete/query
* `context`: request origin, time window, task origin

Start with deny-by-default evaluation for mutating actions when a policy exists.

## Worker/task enforcement

* Propagate actor and tenant context when queuing tasks.
* Re-evaluate authorization in worker entrypoints before applying mutations.
* Emit audit events on policy-denied mutations for traceability.

## Non-goals (initial)

* External policy engines (OPA/Cedar/etc.) in the first increment.
* Cross-tenant/global policy definitions.
* End-user policy authoring UI.
