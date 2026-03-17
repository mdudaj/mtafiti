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
