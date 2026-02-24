# EDMP architecture (scaffold)

This repository is intentionally small: it provides a starting point for a **cloud-native, multi-tenant** enterprise data management platform (EDMP) and a place to evolve the platform design alongside runnable code.

## Goals

* **Kubernetes-native** deployment (stateless app containers; health probes; configuration via env/secrets).
* **Strong tenant isolation** via schema-per-tenant (`django-tenants`).
* **Async-first integration** patterns (event publishing + background tasks).
* A foundation for future EDMP capabilities: ingestion, governance, catalog, lineage, and policy enforcement.

## Current building blocks in this repo

### Multi-tenancy (schema-per-tenant)

* Tenant + domain models live in `backend/tenants/`.
* `EDMPTenantMiddleware` resolves tenants by hostname; requests without a tenant are rejected.
* Each tenant gets an isolated PostgreSQL schema (`auto_create_schema = True`).

### Health / readiness probes (Kubernetes)

Probe endpoints are explicitly treated as public (no tenant required):

* `GET /healthz` and `GET /livez` → always OK (use either for liveness checks)
* `GET /readyz` → performs a DB round-trip (returns `503` if DB is unavailable)

### Eventing (RabbitMQ topic exchange)

`backend/core/events.py` provides:

* `build_event_payload(...)` to standardize event metadata (tenant id, correlation id, timestamp, etc.)
* `publish_event(...)` to publish JSON events to RabbitMQ via `pika`
* Event publishing is enabled when `RABBITMQ_URL` is configured (otherwise it is a no-op).
* See [events design notes](events.md) for the current envelope and routing conventions.

### Background processing (Celery)

Celery is configured in `backend/config/celery.py` and uses `TenantTask` (`backend/core/celery.py`) to enforce that tasks execute inside a tenant schema context.

In Kubernetes, run Celery workers as a separate Deployment (see `deploy/k8s/worker.yaml`) so that web and worker scaling can be tuned independently.

### Metadata catalog (minimal slice)

`backend/core/models.py` includes a `DataAsset` model and a small JSON API:

* `GET /api/v1/assets` (list)
* `POST /api/v1/assets` (create)
* `GET /api/v1/assets/<id>` (get)
* `PUT /api/v1/assets/<id>` (update)

## Target (evolving) platform shape

This is the intended direction for expanding EDMP capabilities:

* **Control plane / API**: tenant administration, metadata APIs, and integration entrypoints.
* **Data plane**: ingestion connectors, transformation jobs, and materialization/serving layers.
* **Metadata plane**: catalog, lineage, ownership, tags/classification.
* **Governance / policy**: RBAC/ABAC, audit events, retention policies, and data access controls.
* **Observability**: logs, metrics, traces; SLOs aligned with readiness/liveness behavior.

## Next design increments (near-term)

This section describes the next pieces to design and implement while keeping the codebase intentionally small.

### API conventions

* Keep APIs versioned under `/api/v1/...`.
* Prefer JSON-only endpoints with explicit error payloads: `{"error": "<code>"}`.
* Tenant-scoped APIs require tenant resolution via hostname (`EDMPTenantMiddleware`).
* Public/control-plane APIs continue to bypass tenant resolution (e.g. `/api/v1/tenants`).
* See `docs/openapi.yaml` for the current HTTP surface (scaffold).

### Identity & access (authn/authz)

Initial implementation can start as a simple header-based identity (for local/dev) and graduate to OIDC:

* **Authentication**: OIDC (JWT) at the edge (Ingress/API gateway) and/or in Django (DRF later, if needed).
* **Authorization**:
  * Control plane: tenant admin actions restricted to platform operators.
  * Tenant plane: scoped roles per tenant (e.g. `catalog.reader`, `catalog.editor`, `policy.admin`).
* **Audit**: emit an audit event for mutating actions (tenant creation, asset changes, policy changes).

### Eventing model

RabbitMQ topic exchange is the first building block.

* Emit domain events for:
  * `tenant.created`
  * `asset.created`, `asset.updated`
* Include consistent metadata using `build_event_payload(...)`:
  * `tenant_id`, `correlation_id`, `user_id`, `timestamp`
* Routing keys should follow a predictable convention:
  * `<tenant_id>.<domain>.<event>` (example: `t_1234.catalog.asset.updated`)

### Ingestion & integration entrypoints

Design for connector-style ingestion without coupling to any single tool:

* HTTP ingestion endpoint(s) (future): accept metadata payloads and enqueue processing.
* Celery tasks: perform normalization, validation, and persistence inside tenant schema.
* Long-running/large ingestions: move to job-style execution (Kubernetes Jobs) while keeping the API surface stable.

### Catalog expansion (incremental)

Keep `DataAsset` minimal, but design for:

* Stable identifiers (`id` UUID) and immutable `asset_type`
* Qualified name uniqueness (likely per tenant + asset_type in the future)
* Optional fields: description, owner, tags, classifications
* Relationship graph (future): lineage edges between assets (table → dashboard, dataset → model, etc.)

### Observability & SLOs

* Probes:
  * `/livez`: process-level OK
  * `/readyz`: dependency-level OK (DB round-trip)
* Logging: JSON logs with correlation id when present (ingress can inject `X-Correlation-Id`)
* Metrics (future): expose `/metrics` (Prometheus) and track queue depth, task latency, request latency.
