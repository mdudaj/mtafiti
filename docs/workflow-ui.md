# Workflow engine and UI design notes

This note defines how Mtafiti uses Viewflow and django-material as the Django-native workflow UI stack.

## Goals

* Keep workflow execution and UI in a single Django runtime boundary.
* Use Viewflow for approval/state-machine style flows first, before adding external engines.
* Keep UI server-rendered (django-material) with progressive enhancement only.

## Framework constraints

* Workflow engine: **Viewflow**.
* Frontend framework: **django-material** with Viewflow-compatible templates.
* No SPA rewrite for core workflow screens in this increment.

## Navigation contract

Primary tenant navigation should remain:

`Dashboard | Projects | Labels | Documents | Workflows | Connectors | Notebooks | Administration | Audit Logs`

Rules:

* Menu visibility is role-based and tenant-scoped.
* Workflow actions (submit/review/approve/reject) must enforce role checks server-side.
* Every mutating workflow transition emits audit/event entries with correlation id.

## Initial workflow model

* Support explicit states (`draft`, `in_review`, `approved`, `active`, `superseded`, `rolled_back`) where domain-appropriate.
* Keep transition logic in Django services, with Viewflow orchestrating task progression and assignee routing.
* Use tenant-safe task execution conventions from `docs/request-context.md` and `docs/policy.md`.

## Non-goals (this increment)

* External workflow engines replacing Viewflow.
* Client-heavy SPA workflow designer.

## API and lifecycle (implemented scaffold slice)

Endpoints:

* `GET/POST /api/v1/workflows/definitions`
* `GET /api/v1/workflows/definitions/<definition_id>`
* `GET/POST /api/v1/workflows/runs`
* `POST /api/v1/workflows/runs/<run_id>/transition`
* `GET /api/v1/workflows/runs/<run_id>/tasks`

Workflow transitions:

* `draft -> in_review` (`submit`)
* `in_review -> approved|rejected` (`approve|reject`)
* `approved -> active|rolled_back` (`activate|rollback`)
* `active -> superseded|rolled_back` (`supersede|rollback`)

Role enforcement:

* Definition create: `policy.admin|tenant.admin`
* Run create/submit: `catalog.editor|tenant.admin`
* Review/approval transitions: `policy.admin|tenant.admin`

## Next UI phase scope (implemented tracking slice)

This phase defines UI requirements for operational visibility over newly delivered backend slices.

Primary additions:

* **Operations dashboard widgets**
  * stewardship queue summary (`open`, `in_review`, `blocked`, `resolved`)
  * orchestration run summary (`queued`, `running`, `succeeded`, `failed`, `cancelled`)
  * agent run summary (`queued`, `running`, `completed`, `failed`, `cancelled`, `timed_out`)
* **Stewardship workbench**
  * list/filter/assign/transition stewardship items
  * resolution capture and status timeline
* **Orchestration monitor**
  * workflow catalog and run history
  * run-step result inspection and cancellation control
* **Agent run monitor**
  * run queue/history view with status and timeout/cancel visibility

## API-to-UI mapping

* Stewardship queue panel
  * `GET /api/v1/stewardship/items`
  * `POST /api/v1/stewardship/items/<item_id>/transition`
* Orchestration panel
  * `GET/POST /api/v1/orchestration/workflows`
  * `GET/POST /api/v1/orchestration/runs`
  * `POST /api/v1/orchestration/runs/<run_id>/transition`
* Agent run panel
  * `GET/POST /api/v1/agent/runs`
  * `POST /api/v1/agent/runs/<run_id>/transition`
* Workflow baseline panel
  * `GET/POST /api/v1/workflows/definitions`
  * `GET/POST /api/v1/workflows/runs`
  * `GET /api/v1/workflows/runs/<run_id>/tasks`
  * `POST /api/v1/workflows/runs/<run_id>/transition`

## Role-based visibility matrix

* `catalog.reader`
  * read-only visibility for workflow/orchestration/stewardship/agent lists
  * no mutating controls rendered
* `catalog.editor`
  * workflow run submit/create controls
  * orchestration run queue controls
  * stewardship create controls
* `policy.admin` and `tenant.admin`
  * full transition controls (approve/reject/cancel/resolve/assign)
  * administrative visibility over all operational dashboards

All mutating controls must be backed by server-side role checks regardless of UI state.

## Tenant isolation constraints and UI test scenarios

Constraints:

* UI list pages must only render tenant-local records returned by tenant-scoped APIs.
* Deep-link detail pages must handle cross-tenant ids as not found.
* Dashboard aggregates must be computed from tenant-local API responses only.

UI-facing test scenarios:

1. Tenant A and Tenant B load operations dashboards and see different counts/items.
2. Tenant B cannot transition Tenant A stewardship/orchestration/agent/workflow resources.
3. Cross-tenant deep link returns empty/not found state without data leakage.
4. Role downgrade hides controls and server rejects direct mutation attempts.

## Acceptance checks for this phase

1. Every operational UI surface has explicit API mapping and role rules.
2. Tenant isolation scenarios are documented and traceable to API behavior.
3. Usability-critical flows are defined:
   * claim/resolve stewardship item
   * queue/start/cancel orchestration run
   * inspect and cancel/timeout-manage agent run
4. Documentation is sufficient to implement screens without additional scope discovery.

## Operational UI API support (implemented scaffold increment)

To enable UI implementation with a stable backend contract, Mtafiti now provides UI-focused operational endpoints:

* `GET /api/v1/ui/operations/dashboard`
  * returns summary cards for stewardship/workflow/orchestration/agent statuses
  * supports optional `project_id` filtering for project-scoped domains
* `GET /api/v1/ui/operations/stewardship-workbench`
  * returns stewardship queue items with computed `allowed_actions` per item
* `GET /api/v1/ui/operations/orchestration-monitor`
  * returns orchestration workflows/runs + capability flags
  * supports optional `project_id` filtering
* `GET /api/v1/ui/operations/agent-monitor`
  * returns agent run history + capability flags
  * supports optional `project_id` filtering

This keeps UI rendering concerns decoupled from domain mutation APIs while preserving server-side role enforcement.

## django-material implementation baseline (new)

To deliver modern SaaS-style operations screens (Slack/Google Drive-like density and navigation) without replacing the backend API contract:

* Keep existing `/api/v1/ui/operations/*` endpoints as the source of truth.
* Add server-rendered HTML routes under `/ui/operations/*` that consume the same payloads.
* Use `django-material` as an optional presentation layer (`EDMP_UI_MATERIAL_ENABLED=true`) with a safe fallback template for environments where the package is not enabled.
* Enforce the same role checks and tenant isolation on HTML routes as API routes.
* Include modern UX baselines by default: summary-first cards, filter toolbars, accessible skip-link/focus behavior, and responsive navigation.
* Provide inline action controls for operational transitions and show consistent success/error feedback banners after action execution.

This enables incremental rollout: API-first remains stable while UI pages mature independently.
