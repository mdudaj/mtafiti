# Identity & access design notes

This scaffold intentionally ships without a full authentication/authorization stack. The goal is to keep the backend deployable in Kubernetes while making the path to enterprise identity predictable.

## Goals

* Support **OIDC/JWT** as the primary authentication mechanism.
* Keep tenant isolation strong: auth decisions should be **tenant-aware**.
* Make authorization explicit and auditable (deny by default for mutating actions).

## Initial implementation (local/dev)

For local development and early integration testing, a simple header-based identity is sufficient:

* `X-User-Id`: stable user identifier (string)
* `X-User-Roles`: comma-separated roles (e.g. `catalog.reader,catalog.editor`)

These headers should be injected by an ingress/gateway in non-dev environments, not trusted from the public internet.

## Target implementation (OIDC)

### Where to validate JWTs

Prefer validation at the edge (Ingress/API gateway) and forward selected claims as headers:

* `X-User-Id`
* `X-User-Email` (optional)
* `X-User-Roles` (optional; see below)
* `X-Correlation-Id` (already supported)

If edge validation is not available, validate JWTs in Django and produce the same request context.

### Token claims (suggested)

* `sub`: user id
* `email`: optional
* `tid` (or similar): tenant id for tenant-scoped calls (optional; hostname still drives tenant resolution)
* `roles`: array of role strings (tenant-scoped roles recommended)

## Authorization model (RBAC first)

Start with a small set of roles and expand later:

* `tenant.admin`: tenant admin actions (within a tenant)
* `catalog.reader`: read catalog assets
* `catalog.editor`: create/update assets
* `policy.admin`: manage policies (future)

When the API grows, move toward ABAC (attributes like classification, ownership, purpose) while preserving the role model for coarse access boundaries.

