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

Role checks are currently **opt-in** for easier incremental rollout:

* Set `EDMP_ENFORCE_ROLES=true` to enforce role checks on mutating APIs.
* Mutating APIs currently require:
  * `tenant.admin` for `POST /api/v1/tenants`
  * `catalog.editor` for `POST/PUT /api/v1/assets`, `POST /api/v1/ingestions`, and `POST /api/v1/lineage/edges`

These headers should be injected by an ingress/gateway in non-dev environments, not trusted from the public internet.

## Target implementation (OIDC)

### Where to validate JWTs

Prefer validation at the edge (Ingress/API gateway) and forward selected claims as headers:

* `X-User-Id`
* `X-User-Email` (optional)
* `X-User-Roles` (optional; see below)
* `X-Correlation-Id` (already supported)

If edge validation is not available, validate JWTs in Django and produce the same request context.

### Current hardening path in scaffold

The backend now supports HS256 bearer token validation in middleware for `/api/*` routes:

* `Authorization: Bearer <jwt>` parsing and signature validation.
* Registered claim checks: `sub`, `exp`/`nbf` (when present), optional `iss` and `aud`.
* Claim mapping:
  * `sub` -> `X-User-Id`
  * `roles` (array or comma-separated string) -> `X-User-Roles`
  * optional `tid` checked against resolved tenant schema (mismatch => `403`).

Configuration:

* `EDMP_OIDC_REQUIRED=true|false` (when true, missing bearer token returns `401` on API routes).
* `EDMP_OIDC_JWT_SECRET=<shared-secret>` (required for in-app HS256 validation).
* `EDMP_OIDC_ISSUER=<issuer>` (optional strict match).
* `EDMP_OIDC_AUDIENCE=<aud1,aud2>` (optional allowed audience set).

Fallback behavior:

* When `EDMP_OIDC_REQUIRED=false`, requests without bearer tokens can still use header-based identity for local/dev.
* When a bearer token is present but invalid, request is rejected (`401`) instead of falling back.

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
