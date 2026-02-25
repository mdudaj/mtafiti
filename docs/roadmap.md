# EDMP roadmap (design increments)

This repository is an intentionally small scaffold. This roadmap lists the next design increments that expand EDMP capabilities while keeping the runtime and operational surface area minimal.

## Delivered in this scaffold

1. **Identity (authn) + roles (authz)**: basic role checks with clear OIDC/JWT integration points (see `docs/identity.md`).
2. **Governance foundations**: initial governance and policy design baseline for roles, metadata classifications, and audit conventions (see `docs/governance.md`).
3. **Catalog growth**: optional asset fields (`description`, `owner`, `tags`, `classifications`) on the minimal API.
4. **Lineage graph**: tenant-scoped edge upsert/query conventions (see `docs/lineage.md`).
5. **Ingestion framework**: ingestion request/status API as the base integration entrypoint (see `docs/ingestion.md`).
6. **Eventing conventions**: optional RabbitMQ-backed domain-event publishing and routing-key conventions (see `docs/events.md`).
7. **Observability baseline**: health/readiness probes and structured logging with correlation ids (see `docs/observability.md`).

## Near-term (next)

1. **Audit events**: emit consistent audit events for mutating actions (tenants, assets, lineage, policies) (see `docs/audit.md`).
2. **Policy enforcement**: RBAC/ABAC checks in API handlers and background tasks, integrated with identity (see `docs/policy.md`).
3. **Request context propagation**: define correlation/user/tenant context capture and async propagation conventions (see `docs/request-context.md`).
4. **Search**: metadata search (indexing strategy + query API) while keeping tenant isolation intact (see `docs/search.md`).
5. **Metrics**: add `/metrics` (Prometheus) and define initial SLOs for API and worker workloads (see `docs/metrics.md`).
6. **Data quality**: define tenant-scoped quality rules, evaluation lifecycle, and result/event conventions (see `docs/data-quality.md`).
7. **Data contracts**: define tenant-scoped schema/expectation contracts and lifecycle conventions for producer-consumer alignment (see `docs/data-contracts.md`).
8. **Retention lifecycle**: define tenant-scoped retention rules, hold/approval flow, and archive/delete event conventions (see `docs/retention.md`).

## Mid-term

* **Connector execution model**: expand ingestion into connector plugins and job-style long-running execution paths (see `docs/connectors.md`).
* **Governance depth**: policy lifecycle workflows (review/approve/rollback) and stronger classification controls (see `docs/governance-workflows.md`).
* **Reference data management**: define tenant-scoped reference datasets, change control, and asset linkage conventions (see `docs/reference-data.md`).
* **Master data management**: define tenant-scoped canonical entity records, survivorship rules, and stewardship conventions (see `docs/master-data.md`).
* **Data classification taxonomy**: define tenant-scoped sensitivity levels and lifecycle conventions used by policy, retention, and stewardship flows (see `docs/classification.md`).
* **Business glossary**: define tenant-scoped business terms, ownership, and asset-linking conventions (see `docs/glossary.md`).
* **Data products**: define tenant-scoped product metadata, ownership, and lifecycle conventions built on existing catalog and governance foundations (see `docs/data-products.md`).
* **Data stewardship operations**: define tenant-scoped stewardship queues, assignment/triage lifecycle, and resolution events across governance domains (see `docs/stewardship.md`).
* **Workflow orchestration**: define lightweight scheduled/event-driven workflow runs built on connector executions (see `docs/orchestration.md`).

## Out of scope for this scaffold (yet)

* Full external workflow engine adoption (Airflow/Argo/etc.) — prefer clean integration points first (see `docs/orchestration.md`).
* Large-scale data lake/warehouse provisioning — EDMP should integrate with existing compute/storage layers.
