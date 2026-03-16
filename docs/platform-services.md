# Platform services design notes

This note captures the required shared services baseline for the Mtafiti platform on Kubernetes.

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

## Implemented scaffold baseline

This scaffold now includes a Helm chart at `deploy/helm/mtafiti-platform` with:

* templated Mtafiti application Deployment + Service
* templated worker Deployment
* templated migration Job (`migrate_schemas --noinput`)
* templated PostgreSQL StatefulSet + Service
* templated RabbitMQ Deployment + Service
* templated ingress for control-plane and wildcard tenant hosts
* baseline platform-services ConfigMap for Redis, MinIO, Keycloak, ONLYOFFICE, JupyterHub, Prometheus, Grafana, Loki, and Sentry endpoint wiring
* security-default wiring for secret-backed broker URLs, pod/container security contexts, and NetworkPolicy boundaries

Use this as the default packaging baseline:

```bash
helm upgrade --install mtafiti-platform deploy/helm/mtafiti-platform -n edmp --create-namespace
```

## Storage and identity conventions

* MinIO buckets/prefixes are tenant-scoped for document/notebook/object artifacts.
* Keycloak provides OIDC tokens/claims used by gateway + app role mapping.
* Service credentials and signing keys are rotated and not embedded in images.

## Non-goals (this increment)

* Full production runbooks for each dependency.
* Cloud-vendor-specific managed service templates.

## Operational response

For operator first-response procedures and incident checkpoints, see [operations runbooks](operations-runbooks.md).

## Portal and domain setup runbook (baseline)

Primary domain topology under `edmp.co.tz`:

* Shared platform services on designated subdomains (`odk`, `odkx`, `redcap`, `rapidsms`, `onlyoffice`).
* Tenant workspace entry at `[tenant].edmp.co.tz`.
* Tenant vertical systems at `[tenant].[lab].edmp.co.tz` and `[tenant].[edcs].edmp.co.tz`.

Current backend routing baseline:

* Explicit domain match via tenant domain records.
* Tenant service-route registry (`/api/v1/tenants/services`) for enabled service mappings.
* Host fallback resolver supports:
  * `service.tenant.base-domain`
  * `tenant.service.base-domain`
  * `tenant.base-domain` (resolved via tenant_slug on enabled service routes)

Operator checklist:

1. Set `EDMP_BASE_DOMAIN=edmp.co.tz` in environment.
2. Create tenant and primary domain.
3. Register tenant service routes for enabled tenant systems (`lab`, `edcs`, workspace-linked services).
4. Validate host resolution with smoke checks on `/` and `/app` for each intended domain pattern.
