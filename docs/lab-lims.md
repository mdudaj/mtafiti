# Research Lab Information Management System (LIMS)

Status: Initial tenant-aware shell and routing scaffold is in progress.

## Purpose

This document defines the target tenant-aware LIMS service exposed at:

- `lims.<tenant>.mtafiti.apps.nimr.or.tz`

## Scope (to be detailed)

- Laboratory workflow modules and operator shell
- Sample lifecycle and chain-of-custody
- Instrument/result integrations
- Role and permission model
- Audit and compliance controls

## Current scaffold

- Tenant-scoped Django app: `src/lims/`
- API namespace: `/api/v1/lims/*`
- HTML shell entrypoint: `/lims/`
- Service-aware routing via `TenantServiceRoute` records for `service_key="lims"`
- Permission model helpers in `src/lims/permissions.py` define module roles, legacy-role compatibility, and guardian-compatible object permission names.

## Permission model

The current LIMS permission slice standardizes four module roles:

- `lims.operator`
- `lims.manager`
- `lims.qa`
- `lims.admin`

These roles map to guardian-compatible object permission names so future Viewflow task nodes can use stable permission codenames even before full `django-guardian` runtime integration is enabled.

### Core permission bundles

- `lims.dashboard.view`
- `lims.reference.view`
- `lims.reference.manage`
- `lims.workflow_task.view`
- `lims.workflow_task.execute`
- `lims.workflow_task.assign`
- `lims.workflow_task.approve`
- `lims.artifact.view`
- `lims.artifact.manage`

### Guardian / Viewflow conventions

- Guardian-compatible names are exposed as `lims.<codename>`, for example:
  - `lims.view_reference_record`
  - `lims.execute_workflow_task`
  - `lims.approve_workflow_task`
- Viewflow task actions should bind to the workflow-task permission family:
  - `view`
  - `execute`
  - `assign`
  - `approve`

### Legacy role compatibility

To preserve current platform behavior while the dedicated LIMS roles are adopted, these existing roles are recognized by the LIMS permission model:

- `catalog.reader`
- `catalog.editor`
- `policy.admin`
- `tenant.admin`

## Integration contracts (to be detailed)

- Shared identity and tenant context from Mtafiti platform
- Eventing and API integrations with workspace services
- Printing and document management touchpoints

## Non-functional requirements (to be detailed)

- Availability and performance targets
- Data residency and retention requirements
- Security and observability requirements

## Open questions

- Detailed domain model and workflow states
- External systems and protocol support
- Migration and rollout strategy per tenant
