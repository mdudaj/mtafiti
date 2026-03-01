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
40. **Audit events**: added consistent audit event emission for mutating actions across core APIs with documented payload shape and validation gates (see `docs/audit.md`).
41. **Policy enforcement**: added role-based authorization checks for API handlers and transition endpoints, integrated with identity context (see `docs/policy.md`).
42. **Request context propagation**: added correlation/user/request/tenant context capture and propagation across middleware, logging, events, and tenant Celery tasks (see `docs/request-context.md`).
43. **Search**: added tenant-scoped metadata search endpoint with query normalization and role checks (see `docs/search.md`).
44. **Metrics**: added Prometheus `/metrics` endpoint with API and worker instrumentation baseline (see `docs/metrics.md`).
45. **Data quality**: added tenant-scoped quality rule lifecycle and evaluation result APIs with quality event/audit conventions (see `docs/data-quality.md`).
46. **Data contracts**: added tenant-scoped contract lifecycle APIs with activation/deprecation and producer-consumer compatibility guardrails (see `docs/data-contracts.md`).
47. **Retention lifecycle**: added tenant-scoped retention rule/hold/run APIs with release flow and archive/delete execution conventions (see `docs/retention.md`).
48. **Identity lifecycle expansion**: added tenant-scoped user directory/profile state APIs plus project membership lifecycle endpoints (role changes, revoke/reactivate) with role-history tracking (see `docs/identity-lifecycle.md`).
49. **Notification delivery hardening**: added notification provider/retry/dead-letter model fields with queue dispatch/retry APIs and delivery status visibility (see `docs/notification-delivery.md`).
50. **Invitation security hardening**: added invite revoke/resend APIs, hashed token storage at rest, and strict TTL/attempt enforcement for one-time login links (see `docs/invitation-security.md` and `docs/project-membership.md`).
51. **Scalability follow-through**: added high-volume index coverage for list/filter hot paths and expanded baseline latency checks for notification queue listing (see `docs/performance-baseline.md`).
52. **CI/test throughput optimization**: increased shard parallelism, split performance baseline into a dedicated CI lane, and documented faster local feedback commands (see `README.md` and `docs/performance-baseline.md`).
53. **Self-reflective delivery workflow**: added concrete issue/PR execution templates and wired workflow docs to enforce issue/handoff contract and shared acceptance checks (see `docs/self-reflective-implementation.md` and `.github/ISSUE_TEMPLATE/delivery-work-item.md`).
54. **Notification provider integration**: added webhook HTTP delivery execution with timeout/error mapping and provider-focused dispatch regression coverage (see `docs/notification-delivery.md`).
55. **Webhook signing for provider delivery**: added optional HMAC request signing for webhook notifications with signature regression tests and configuration docs (see `docs/notification-delivery.md`).
56. **OpenAPI parity expansion for identity/notification/membership APIs**: documented newly delivered user directory, notification dispatch/retry, and project membership invitation lifecycle endpoints and expanded drift-gate coverage for these critical routes/schemas (see `docs/openapi.yaml` and `.github/scripts/check_openapi_contract.py`).
57. **Contract regression coverage for new identity/notification/membership APIs**: expanded API versioning contract tests to assert stable response fields for user directory, notification dispatch, project membership lifecycle, and invitation resend/revoke flows (see `backend/tests/test_api_versioning_contracts.py`).
58. **Pagination envelope parity for list endpoints**: aligned OpenAPI and contract tests so user, notification, and project-membership list APIs consistently declare and verify `items`, `page`, `page_size`, and `total` response fields (see `docs/openapi.yaml`, `.github/scripts/check_openapi_contract.py`, and `backend/tests/test_api_versioning_contracts.py`).
59. **Contract regression coverage for invitation accept and notification retry**: extended API versioning contract tests to assert stable response fields for invitation token acceptance and notification retry responses, including failure/retry path coverage (see `backend/tests/test_api_versioning_contracts.py`).
60. **Error envelope contract coverage for invitation/notification failures**: expanded API versioning contract tests to assert stable `{ "error": ... }` payload shape and version header behavior for invitation accept and notification retry failure responses (see `backend/tests/test_api_versioning_contracts.py`).
61. **Role-enforcement contract coverage for identity/notification/member APIs**: expanded API versioning contract tests with `EDMP_ENFORCE_ROLES` enabled to verify stable forbidden error envelopes and allowed list response contracts for user directory, notification dispatch, and project member listing endpoints (see `backend/tests/test_api_versioning_contracts.py`).
62. **OIDC/JWT coverage for new identity/notification/member APIs**: expanded OIDC auth tests to verify required-bearer behavior and role-gated access across user directory, notification dispatch, and project member list endpoints under `EDMP_OIDC_REQUIRED` + `EDMP_ENFORCE_ROLES` (see `backend/tests/test_oidc_jwt_auth.py`).
63. **OIDC/JWT coverage for invitation accept and notification retry**: expanded OIDC auth tests to verify invitation accept requires bearer authentication and notification retry remains role-gated under `EDMP_OIDC_REQUIRED` + `EDMP_ENFORCE_ROLES` (see `backend/tests/test_oidc_jwt_auth.py`).
64. **OIDC auth response version-header coverage**: expanded OIDC auth tests to verify `X-API-Version: v1` is consistently returned on auth failures and role-gated errors across user directory, invitation accept, and notification dispatch/retry endpoints (see `backend/tests/test_oidc_jwt_auth.py`).
65. **OIDC tenant-claim mismatch coverage for new endpoints**: expanded OIDC auth tests to verify `token_tenant_mismatch` enforcement (and version header behavior) on user directory and invitation accept endpoints when bearer token tenant claim does not match the active tenant schema (see `backend/tests/test_oidc_jwt_auth.py`).
66. **OIDC claim-validation coverage for new endpoints**: expanded OIDC auth tests to verify expired-token, invalid-audience, and invalid-issuer failures (with version header behavior) across user directory, notification dispatch, and invitation accept endpoints (see `backend/tests/test_oidc_jwt_auth.py`).
67. **OIDC bearer/role enforcement coverage for invitation admin endpoints**: expanded OIDC auth tests to verify revoke/resend invitation endpoints enforce bearer authentication, reject insufficient roles, and allow editor-authorized control flow under `EDMP_OIDC_REQUIRED` + `EDMP_ENFORCE_ROLES` (see `backend/tests/test_oidc_jwt_auth.py`).
68. **OIDC subject/nbf validation coverage for new endpoints**: expanded OIDC auth tests to verify invalid subject and not-yet-valid token failures (with version header behavior) on user directory and notification dispatch endpoints (see `backend/tests/test_oidc_jwt_auth.py`).
69. **Project workspace baseline for tool/resource loading**: added tenant-scoped project workspace API to load collaboration, data-management, and document-management resources (including protocol/DMP/SOP-style document metadata), with OpenAPI and regression test coverage (see `backend/core/views.py`, `backend/tests/test_projects_api.py`, and `docs/openapi.yaml`).

## Near-term (next)

No additional near-term items are currently queued in this scaffold.

## Mid-term

No additional mid-term items are currently queued in this scaffold.

## Out of scope for this scaffold (yet)

* Full external workflow engine adoption (Airflow/Argo/etc.) — prefer clean integration points first (see `docs/orchestration.md`).
* Large-scale data lake/warehouse provisioning — EDMP should integrate with existing compute/storage layers.
