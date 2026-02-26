# Workflow engine and UI design notes

This note defines how EDMP uses Viewflow and django-material as the Django-native workflow UI stack.

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
