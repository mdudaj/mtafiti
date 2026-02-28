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
16. **Connector execution model**: connector run lifecycle with worker/job paths, execution progress, and cancellation conventions (see `docs/connectors.md`).
17. **Workflow engine and UI baseline**: workflow definition/run/task lifecycle with server-side transition role checks (see `docs/workflow-ui.md`).
18. **Governance depth**: policy lifecycle workflows (review/approve/rollback) and stronger classification controls (see `docs/governance-workflows.md`).
19. **Platform services baseline**: Helm-managed core service packaging for backend, worker, migrations, ingress, and dependency service wiring (see `docs/platform-services.md`).
20. **Platform security hardening**: Helm-level secret handling, pod security contexts, and network-policy boundaries for core services (see `docs/platform-security.md`).
21. **Business glossary**: tenant-scoped term lifecycle, ownership, and asset-linking APIs with glossary event/audit conventions (see `docs/glossary.md`).
22. **Data products**: tenant-scoped product metadata and lifecycle APIs with activation guardrails tied to active data contracts (see `docs/data-products.md`).
23. **Data sharing**: tenant-scoped provider/consumer share lifecycle APIs with constraint validation, expiry handling, and revocation conventions (see `docs/data-sharing.md`).
24. **Metadata versioning**: tenant-scoped asset metadata version lifecycle with draft/publish/supersede flow and publish validation gates (see `docs/metadata-versioning.md`).
25. **Data privacy management**: tenant-scoped privacy profile, consent, and privacy-action lifecycle APIs with policy/retention/stewardship integration hooks (see `docs/privacy.md`).
26. **Agentic AI execution**: tenant-scoped agent run lifecycle APIs with tool allowlisting, timeout/cancel controls, and execution audit/event conventions (see `docs/agentic-ai.md`).
27. **Data stewardship operations**: tenant-scoped stewardship queue item APIs with assignment/triage/resolution lifecycle and stewardship event/audit conventions (see `docs/stewardship.md`).
28. **Workflow orchestration**: lightweight tenant-scoped orchestration workflow/run APIs with schedule/event triggers, connector-backed step execution, and orchestration event/audit conventions (see `docs/orchestration.md`).
29. **User interface expansion tracking**: defined next UI phase scope, API-to-UI mappings, role visibility matrix, tenant isolation scenarios, and acceptance checks for operational dashboards (see `docs/workflow-ui.md`).
30. **API versioning conventions**: documented version/deprecation policy, migration guidance, and response contract regression checks (see `docs/api-versioning.md`).
31. **Event/audit schema validation gates**: added schema validation for workflow/orchestration/stewardship/agent/audit event families with regression tests that fail on contract drift (see `docs/events.md` and `docs/audit.md`).
32. **Performance and scale baseline**: defined repeatable API/worker load profiles with measurable latency/error thresholds and documented next optimization path (see `docs/performance-baseline.md`).
33. **OIDC/JWT hardening**: added bearer token validation, issuer/audience checks, claim mapping to user/roles context, tenant-claim guardrails, and invalid-token failure tests (see `docs/identity.md` and `docs/policy.md`).
34. **Operational runbooks and incident playbooks**: documented first-response runbooks for connector failures, orchestration failures, and queue backlog incidents with verification commands and safety notes (see `docs/operations-runbooks.md`).
35. **OIDC rollout and key rotation operations**: documented phased `EDMP_OIDC_REQUIRED` rollout, JWT secret rotation sequence, smoke checks, and rollback guidance for operators (see `docs/operations-runbooks.md` and `docs/identity.md`).
36. **Pagination and list endpoint performance hardening**: added bounded default pagination and page-size caps for high-volume list APIs with pagination regression and baseline latency checks (see `docs/performance-baseline.md`).
37. **Operational dashboards and alert rules**: defined dashboard panels for API/worker/queue health, alert severities and thresholds, and explicit alert-to-runbook triage mappings (see `docs/operations-dashboards-alerts.md`).
38. **API contract drift gates and consumer safety checks**: added OpenAPI-to-route/schema drift checks, expanded critical contract regression tests, and standardized API change/deprecation communication checklist (see `docs/api-versioning.md` and `docs/api-change-management.md`).
39. **Project membership invitation workflow**: added project role invites (`principal_investigator`, `researcher`, `data_manager`) with existing-user notifications, one-time login invite links for new users, and acceptance flow (see `docs/project-membership.md`).

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

* **Self-reflective delivery workflow**: define implementation-agent roles, handoff contracts, retry budgets, and quality gates for faster feature delivery (see `docs/self-reflective-implementation.md`).

## Out of scope for this scaffold (yet)

* Full external workflow engine adoption (Airflow/Argo/etc.) — prefer clean integration points first (see `docs/orchestration.md`).
* Large-scale data lake/warehouse provisioning — EDMP should integrate with existing compute/storage layers.
