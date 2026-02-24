# Kubernetes deployment notes (scaffold)

This project’s backend is designed to run as a stateless service in Kubernetes. The manifests in `deploy/k8s/` are **examples** to help bootstrap the platform design.

## Health probes

The Deployment example uses:

* liveness: `GET /livez`
* readiness: `GET /readyz`

These endpoints do **not** require tenant host resolution.

## Example manifests

See:

* `deploy/k8s/backend.yaml`
* `deploy/k8s/worker.yaml`
* `deploy/k8s/migrate-job.yaml`

Notes:

* Provide PostgreSQL connectivity via `POSTGRES_*` env vars.
* Provide broker connectivity via:
  * `CELERY_BROKER_URL` (Celery/RabbitMQ)
  * `RABBITMQ_URL` (domain event publishing; can be the same as `CELERY_BROKER_URL`)
* `DJANGO_SECRET_KEY` should be provided via a Kubernetes Secret.

## Recommended runtime components (logical)

Even if initially deployed as a single pod, the platform design assumes these components:

* **web** (Django): serves HTTP APIs; stateless.
* **worker** (Celery): executes background tasks (tenant-scoped via `TenantTask`).
* **broker** (RabbitMQ): topic exchange for events + Celery broker (can be separated later).
* **postgres**: shared DB with schema-per-tenant isolation.

## Migrations / tenant schema lifecycle

For `django-tenants`, schema creation happens on tenant creation (`auto_create_schema = True`).
Operationally in Kubernetes:

* Run migrations as a **Job** during deploys (or an init container), before scaling web/worker.
  * Example: `deploy/k8s/migrate-job.yaml`
* Ensure readiness probes only pass after DB is reachable (`/readyz` already checks this).

## Configuration & secrets

* Store secrets (DB password, `DJANGO_SECRET_KEY`, broker credentials) in a **Secret**.
* Store non-secret config (allowed hosts, log level, broker URL without creds) in a **ConfigMap**.
* Prefer separate variables for broker URL/user/pass if you plan to rotate credentials without editing URLs.

## Ingress / host-based tenant routing

Tenant resolution is host-based. In Kubernetes, ensure:

* Ingress forwards the original `Host` header to the service.
* Wildcard DNS / wildcard TLS is configured for tenant domains (e.g. `*.tenant.example.com`).
* A control-plane hostname (e.g. `control.example.com`) exists for `/api/v1/tenants`.

## Scaling

* Scale web horizontally with a Deployment + HPA (CPU + request rate if available).
* Scale workers independently (queue depth / task latency metrics are ideal for HPA).
* Use separate Deployments for web and worker to avoid resource contention.

## Network policy (future)

If using NetworkPolicies:

* Allow web/worker egress only to Postgres and RabbitMQ.
* Allow ingress only from Ingress controller / gateway.
