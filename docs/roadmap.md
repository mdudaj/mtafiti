# EDMP roadmap (design increments)

This repository is an intentionally small scaffold. This roadmap lists the next design increments that expand EDMP capabilities while keeping the runtime and operational surface area minimal.

## Delivered in this scaffold

1. **Identity (authn) + roles (authz)**: basic role checks with clear OIDC/JWT integration points (see `docs/identity.md`).
2. **Catalog growth**: optional asset fields (`description`, `owner`, `tags`, `classifications`) on the minimal API.
3. **Lineage graph**: tenant-scoped edge upsert/query conventions (see `docs/lineage.md`).
4. **Ingestion framework**: ingestion request/status API as the base integration entrypoint (see `docs/ingestion.md`).
5. **Observability baseline**: health/readiness probes and structured logging with correlation ids (see `docs/observability.md`).

## Near-term (next)

1. **Audit events**: emit consistent audit events for mutating actions (tenants, assets, lineage, policies) (see `docs/audit.md`).
2. **Policy enforcement**: RBAC/ABAC checks in API handlers and background tasks, integrated with identity (see `docs/policy.md`).
3. **Search**: metadata search (indexing strategy + query API) while keeping tenant isolation intact (see `docs/search.md`).
4. **Metrics**: add `/metrics` (Prometheus) and define initial SLOs for API and worker workloads (see `docs/metrics.md`).

## Mid-term

* **Connector execution model**: expand ingestion into connector plugins and job-style long-running execution paths (see `docs/connectors.md`).
* **Governance depth**: policy lifecycle workflows (review/approve/rollback) and stronger classification controls (see `docs/governance-workflows.md`).

## Out of scope for this scaffold (yet)

* Full workflow orchestration and scheduling (Airflow/Argo/etc.) — prefer clean integration points first.
* Large-scale data lake/warehouse provisioning — EDMP should integrate with existing compute/storage layers.
