# Platform services design notes

This note captures the required shared services baseline for the EDMP platform on Kubernetes.

## Goals

* Document the mandatory runtime components and their responsibility boundaries.
* Keep deployment approach consistent with Helm-managed Kubernetes operations.
* Clarify service roles used by current and planned design increments.

## Core services baseline

* Django API + worker workloads
* PostgreSQL (schema-per-tenant)
* RabbitMQ (events + task transport)
* Redis (cache/session support only)
* MinIO (object storage)
* Keycloak (OIDC identity provider)
* ONLYOFFICE (collaborative editing)
* JupyterHub (tenant-scoped notebook control plane)
* Prometheus + Grafana (metrics and dashboards)
* Loki (log aggregation)
* Sentry (application error monitoring)

## Deployment conventions

* Deploy and version workloads via Helm-managed releases.
* Separate web/worker scaling and resource policies.
* Keep externalized configuration and secret references per environment.
* Enforce readiness/liveness contracts before traffic cutover.

## Storage and identity conventions

* MinIO buckets/prefixes are tenant-scoped for document/notebook/object artifacts.
* Keycloak provides OIDC tokens/claims used by gateway + app role mapping.
* Service credentials and signing keys are rotated and not embedded in images.

## Non-goals (this increment)

* Full production runbooks for each dependency.
* Cloud-vendor-specific managed service templates.
