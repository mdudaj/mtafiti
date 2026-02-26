# EDMP roadmap (design increments)

This repository is an intentionally small scaffold. This roadmap lists the next design increments that expand EDMP capabilities while keeping the runtime and operational surface area minimal.

## Delivered in this scaffold

1. **Identity (authn) + roles (authz)**: basic role checks with clear OIDC/JWT integration points (see `docs/identity.md`).
2. **Governance foundations**: initial governance and policy design baseline for roles, metadata classifications, and audit conventions (see `docs/governance.md`).
3. **Catalog growth**: optional asset fields (`description`, `owner`, `tags`, `classifications`) on the minimal API (see `docs/catalog.md`).
4. **Lineage graph**: tenant-scoped edge upsert/query conventions (see `docs/lineage.md`).
5. **Ingestion framework**: ingestion request/status API as the base integration entrypoint (see `docs/ingestion.md`).
6. **Eventing conventions**: optional RabbitMQ-backed domain-event publishing and routing-key conventions (see `docs/events.md`).
7. **Observability baseline**: health/readiness probes and structured logging with correlation ids (see `docs/observability.md`).
8. **Data residency controls**: tenant-scoped residency profile lifecycle and region allow/deny checks with event/audit conventions (see `docs/residency.md`).
9. **Data access requests**: tenant-scoped access request/decision lifecycle with status transitions and audit/event conventions (see `docs/access-requests.md`).
10. **Reference data management**: tenant-scoped reference dataset/version lifecycle with single-active-version activation conventions (see `docs/reference-data.md`).
11. **Master data management**: tenant-scoped canonical master record versioning and merge approval lifecycle (see `docs/master-data.md`).
12. **Data classification taxonomy**: tenant-scoped classification lifecycle with active-only asset assignment conventions (see `docs/classification.md`).
13. **Printing and gateway**: tenant-scoped print job lifecycle with gateway status updates and print events (see `docs/printing.md`).
14. **Collaboration**: tenant-scoped collaborative document metadata, session issuance, and version checkpoint lifecycle (see `docs/collaboration.md`).
15. **Notebook infrastructure**: tenant-scoped notebook workspace/session/execution lifecycle with execution and termination events (see `docs/notebooks.md`).

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
* **Workflow engine and UI baseline**: establish Viewflow-driven lifecycle orchestration and django-material navigation contracts (see `docs/workflow-ui.md`).
* **Governance depth**: policy lifecycle workflows (review/approve/rollback) and stronger classification controls (see `docs/governance-workflows.md`).
* **Platform services baseline**: formalize Helm-managed core services (Keycloak, MinIO, Redis, ONLYOFFICE, JupyterHub, observability stack) (see `docs/platform-services.md`).
* **Platform security hardening**: formalize mTLS, network-policy boundaries, secret handling, and immutable audit controls (see `docs/platform-security.md`).
* **Data privacy management**: define tenant-scoped privacy profiles, consent state handling, and policy/retention integration conventions (see `docs/privacy.md`).
* **Business glossary**: define tenant-scoped business terms, ownership, and asset-linking conventions (see `docs/glossary.md`).
* **Data products**: define tenant-scoped product metadata, ownership, and lifecycle conventions built on existing catalog and governance foundations (see `docs/data-products.md`).
* **Data sharing**: define tenant-scoped provider/consumer share lifecycle, constraint handling, and revocation conventions for governed distribution (see `docs/data-sharing.md`).
* **Metadata versioning**: define tenant-scoped draft/publish/supersede conventions for auditable metadata evolution (see `docs/metadata-versioning.md`).
* **Agentic AI execution**: define tenant-scoped tool governance, timeout controls, and execution audit/event conventions (see `docs/agentic-ai.md`).
* **Self-reflective delivery workflow**: define implementation-agent roles, handoff contracts, retry budgets, and quality gates for faster feature delivery (see `docs/self-reflective-implementation.md`).
* **Data stewardship operations**: define tenant-scoped stewardship queues, assignment/triage lifecycle, and resolution events across governance domains (see `docs/stewardship.md`).
* **Workflow orchestration**: define lightweight scheduled/event-driven workflow runs built on connector executions (see `docs/orchestration.md`).

## Out of scope for this scaffold (yet)

* Full external workflow engine adoption (Airflow/Argo/etc.) — prefer clean integration points first (see `docs/orchestration.md`).
* Large-scale data lake/warehouse provisioning — EDMP should integrate with existing compute/storage layers.
