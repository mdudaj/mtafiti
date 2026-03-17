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
- Reference-domain models and APIs now live directly in `src/lims/models.py` and `src/lims/views.py`.
- Tanzania address metadata sync is implemented as a resumable Celery task backed by `TanzaniaAddressSyncRun`.

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

## Reference domain

The first reference-data slice standardizes:

- `Lab`
- `Study`
- `Site`
- Tanzania address hierarchy:
  - `TanzaniaRegion`
  - `TanzaniaDistrict`
  - `TanzaniaWard`
  - `TanzaniaStreet`

Reference APIs are exposed under:

- `/api/v1/lims/reference/labs`
- `/api/v1/lims/reference/studies`
- `/api/v1/lims/reference/sites`
- `/api/v1/lims/reference/select-options`
- `/api/v1/lims/reference/address-sync-runs`

These endpoints are intended for admin-style CRUD and downstream selector reuse in receiving/workflow forms.

## Configurable metadata schema domain

The next LIMS configuration slice standardizes tenant-local metadata building blocks for sample-type intake forms and workflow-step forms:

- `MetadataVocabulary`
- `MetadataVocabularyItem`
- `MetadataFieldDefinition`
- `MetadataSchema`
- `MetadataSchemaVersion`
- `MetadataSchemaField`
- `MetadataSchemaBinding`

This allows LIMS tenants to define reusable field definitions, publish versioned schemas, and bind a published schema to:

- `sample_type` keys such as `dried-blood-spot`
- `workflow_step` keys such as `dbs-receiving`

Metadata APIs are exposed under:

- `/api/v1/lims/metadata/vocabularies`
- `/api/v1/lims/metadata/field-definitions`
- `/api/v1/lims/metadata/schemas`
- `/api/v1/lims/metadata/schemas/<schema_id>/versions`
- `/api/v1/lims/metadata/schemas/<schema_id>/versions/<version_id>/publish`
- `/api/v1/lims/metadata/bindings`
- `/api/v1/lims/metadata/validate`

Validation is intentionally explicit and repository-native rather than delegated to an external schema engine. The current validation service supports:

- required versus optional fields
- type validation for text, long text, integer, decimal, boolean, date, datetime, choice, and multi-choice fields
- controlled vocabularies for choice-style fields
- min/max or length/item-count range checks
- conditional field activation and requiredness based on earlier field values

This gives the later workflow-configuration and runtime slices a stable tenant-aware schema registry without needing the full workflow-template domain to exist first.

## Biospecimen aggregate

The current biospecimen slice introduces tenant-local specimen and pooling primitives for the first LIMS lifecycle workflows:

- `BiospecimenType`
- `Biospecimen`
- `BiospecimenPool`
- `BiospecimenPoolMember`

Current conventions:

- each sample type owns a configurable identifier/barcode prefix plus padded sequence counter
- specimen IDs and barcodes are allocated transactionally from the sample-type sequence
- aliquots are modeled as child `Biospecimen` records with `parent_specimen` and `lineage_root`
- pools are modeled separately from single-parent lineage so one pool can reference many source specimens
- artifact permissions (`lims.artifact.view` / `lims.artifact.manage`) guard the current biospecimen APIs

The first API surface is exposed under:

- `/api/v1/lims/biospecimen-types`
- `/api/v1/lims/biospecimens`
- `/api/v1/lims/biospecimens/<specimen_id>/transition`
- `/api/v1/lims/biospecimens/<specimen_id>/aliquots`
- `/api/v1/lims/biospecimen-pools`
- `/api/v1/lims/biospecimen-pools/<pool_id>/transition`

This slice standardizes the initial lifecycle statuses:

- `registered`
- `received`
- `available`
- `aliquoted`
- `pooled`
- `consumed`
- `archived`
- `disposed`

These records are intentionally simple JSON APIs for now so later accessioning, batch, QC, and workflow-runtime slices can reuse the same aggregate without waiting for the full Viewflow runtime.

## Accessioning and receiving workflows

The current accessioning slice standardizes the first receiving workflow primitives on top of the biospecimen aggregate:

- `AccessioningManifest`
- `AccessioningManifestItem`
- `ReceivingEvent`
- `ReceivingDiscrepancy`

Current conventions:

- manifests move through `draft`, `submitted`, `receiving`, and `received`
- batch uploads create manifest items first, then receiving updates item state and either creates or binds the final biospecimen
- single-sample receiving is supported through a direct endpoint for scan-oriented or bench-entry workflows
- discrepancies stay explicit records instead of being hidden in free-text notes
- receiving reports are exposed as tenant-local JSON summaries for downstream PDF/export work

The first API surface is exposed under:

- `/api/v1/lims/accessioning/receive-single`
- `/api/v1/lims/accessioning/manifests`
- `/api/v1/lims/accessioning/manifests/<manifest_id>`
- `/api/v1/lims/accessioning/manifests/<manifest_id>/submit`
- `/api/v1/lims/accessioning/manifests/<manifest_id>/items/<item_id>/receive`
- `/api/v1/lims/accessioning/manifests/<manifest_id>/report`
- `/api/v1/lims/receiving/discrepancies`

Metadata validation for receiving continues to reuse the published metadata-schema binding for the relevant biospecimen type, so configurable sample-type intake requirements do not need a separate validation engine.

## Tanzania address sync

Address metadata ingestion is designed to be polite and resumable:

- source: `https://www.tanzaniapostcode.com/`
- hierarchy: `region -> district -> ward -> street -> postcode`
- execution: Celery task in `src/lims/tasks.py`
- persisted checkpoint/state: `TanzaniaAddressSyncRun`

Guardrails:

- each run processes a bounded number of pages (`request_budget`)
- the task persists a queue/checkpoint so later invocations can resume
- `next_not_before_at` enforces a minimum delay between page fetches
- failures are surfaced on the sync run instead of silently dropped

This gives Mtafiti a path to periodic refreshes via Celery Beat or another scheduler without hammering the upstream postcode service.

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
