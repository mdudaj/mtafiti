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

### Background processing (Celery)

Celery is configured in `backend/config/celery.py` and uses `TenantTask` (`backend/core/celery.py`) to enforce that tasks execute inside a tenant schema context.

## Target (evolving) platform shape

This is the intended direction for expanding EDMP capabilities:

* **Control plane / API**: tenant administration, metadata APIs, and integration entrypoints.
* **Data plane**: ingestion connectors, transformation jobs, and materialization/serving layers.
* **Metadata plane**: catalog, lineage, ownership, tags/classification.
* **Governance / policy**: RBAC/ABAC, audit events, retention policies, and data access controls.
* **Observability**: logs, metrics, traces; SLOs aligned with readiness/liveness behavior.
