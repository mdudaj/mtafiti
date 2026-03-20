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
- Admin-style HTML pages:
  - `/lims/`
  - `/lims/reference/`
  - `/lims/metadata/`
  - `/lims/biospecimens/`
  - `/lims/receiving/`
  - `/lims/processing/`
  - `/lims/storage/`
- Service-aware routing via `TenantServiceRoute` records for `service_key="lims"`
- Permission model helpers in `src/lims/permissions.py` define module roles, legacy-role compatibility, and guardian-compatible object permission names.
- Reference-domain models and APIs now live directly in `src/lims/models.py` and `src/lims/views.py`.
- Geography metadata sync is implemented as a resumable Celery task backed by `TanzaniaAddressSyncRun`, with Tanzanian addresses currently serving as the first ingestion source into the generalized geography hierarchy.

The HTML surfaces reuse the shared portal shell in `core/ui/user_base.html` and are intentionally wired to the same JSON APIs used by tests and future automation. This keeps the operator experience admin-style and role-aware without introducing a separate frontend stack.

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

The current reference-data slice standardizes:

- `Lab`
- `Study`
- `Site`
- generalized geography hierarchy:
  - `Country`
  - `Region`
  - `District`
  - `Ward`
  - `Street`
  - `Postcode`

Reference APIs are exposed under:

- `/api/v1/lims/reference/labs`
- `/api/v1/lims/reference/studies`
- `/api/v1/lims/reference/sites`
- `/api/v1/lims/reference/select-options`
- `/api/v1/lims/reference/address-sync-runs`

These endpoints are intended for admin-style CRUD and downstream selector reuse in receiving/workflow forms.

The initial reference page now exposes lab, study, site, and address-sync actions directly from `/lims/reference/` for roles with `lims.reference.manage`, while view-only roles still get the same tables and navigation without mutation controls.

## Configurable metadata schema domain

The next LIMS configuration slice standardizes tenant-local metadata building blocks for sample-type intake forms and workflow-step forms:

- `MetadataVocabularyDomain`
- `MetadataVocabulary`
- `MetadataVocabularyItem`
- `MetadataSchema`
- `MetadataSchemaVersion`
- `MetadataSchemaField`
- `MetadataSchemaBinding`

This allows LIMS tenants to define form metadata, establish a draft version immediately, add fields that belong directly to that version, publish it, and bind the published form to:

- `sample_type` keys such as `dried-blood-spot`
- `workflow_step` keys such as `dbs-receiving`

Metadata APIs are exposed under:

- `/api/v1/lims/metadata/vocabulary-domains`
- `/api/v1/lims/metadata/vocabularies`
- `/api/v1/lims/metadata/vocabularies/provision-defaults`
- `/api/v1/lims/metadata/vocabularies/<vocabulary_id>/items`
- `/api/v1/lims/metadata/field-definitions`
- `/api/v1/lims/metadata/schemas`
- `/api/v1/lims/metadata/schemas/<schema_id>/versions`
- `/api/v1/lims/metadata/schemas/<schema_id>/versions/<version_id>`
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

Vocabulary domains are tenant-scoped and searchable so select and multi-select widgets can resolve the right controlled list by functional category, then fetch filtered items on demand. The current default provisioning pack seeds starter domains and vocabularies for roles, consent, outcomes, biospecimen condition, workflow decisions, and units while still allowing tenants to define additional domains and vocabularies through the same API surface.

Form authoring now follows a two-step flow: create the form definition under `/api/v1/lims/metadata/schemas` to get an initial draft version, then update that draft version through `/api/v1/lims/metadata/schemas/<schema_id>/versions/<version_id>` with version-owned fields. Published versions are immutable; future changes are made by creating a new draft version, optionally cloned from an existing version. Version listings can also be filtered by status so authoring pages can focus on drafts while activation pages only expose published versions.

The first HTML control surface for this slice is `/lims/metadata/`, which provides vocabulary, form, draft-version, publish, and binding actions for users with `lims.metadata.manage`. The form authoring page now supports loading an existing draft, cloning a new draft from a published version, editing version-owned fields, publishing the current draft, and activating a published version for a runtime target such as a biospecimen type.

The emerging ODM-engine foundation now sits beside that transitional metadata registry rather than replacing it in one jump. Compiler-owned form packages are exposed under:

- `/api/v1/lims/form-packages`
- `/api/v1/lims/form-packages/<package_id>`
- `/api/v1/lims/form-packages/<package_id>/versions`
- `/api/v1/lims/form-packages/<package_id>/versions/<version_id>`
- `/api/v1/lims/form-packages/<package_id>/versions/<version_id>/publish`

Those package versions carry canonical sections, item groups, items, choice lists, source-artifact provenance, compiler diagnostics, and compiled projections. A first bootstrap path can materialize a draft package version from an already published `MetadataSchemaVersion`, which keeps current runtime work moving while the compiler-owned package model becomes the long-term contract for workflow/runtime and UI consumers.

The workflow-configuration layer now builds on that contract. Workflow template nodes continue to define bounded Viewflow-style topology plus assignment, permission, and approval metadata, but task capture bindings target published form-package outputs instead of raw metadata-schema versions. Capture scope can therefore be expressed as a whole package, section subsets, item-group subsets, or explicit item subsets while leaving canonical form semantics inside the compiler-owned package model.

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
- biospecimens remain the primary operational artifacts for LIMS workflows; workflow/task capture does not replace them with a graph-native persistence model
- workflow execution should become the governed source of truth for sample quantity/volume acquisition, derivation, storage movement, reservation, and consumption history, with runtime submissions projected into the appropriate domain records

This means the current knowledge graph remains an analysis and coding-assistance artifact, while operational sample, workflow, and inventory state stays in relational tenant-scoped Django/PostgreSQL models.

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

The corresponding operator shell at `/lims/biospecimens/` now exposes sample-type registration, biospecimen creation, and pool assembly forms on top of those APIs.

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

More generally, workflow-administered forms capture task metadata first into runtime submission/audit records. When specific answers have domain meaning, they should then be projected into the corresponding governed models instead of leaving the workflow payload as the only source of truth.

The receiving UX is now split so `/lims/receiving/` acts as a launchpad, while dedicated task pages carry the actual input work:

- `/lims/receiving/single/`
- `/lims/receiving/batch/`
- `/lims/receiving/edc-import/`

This follows the cookbook direction more closely: overview pages remain navigational, and operator input pages present one primary form per task instead of mixing multiple create forms with summary tables.

The accessioning flow on those task pages now models a clearer first-pass lab decision:

- capture initial metadata
- record the first QC outcome (`accept` or `reject`)
- if accepted, log the initial storage placement
- if rejected, capture a discrepancy code and rejection reason

Batch receipt now centers on an Excel-friendly CSV template download/import flow, and the EDC intake page now asks for the lab form, expected sample, and external ID to import before routing the record through the same QC/storage decision.

The single-sample path has now moved one step closer to the intended cookbook-style wizard UX:

- step 1 captures the initial receipt envelope:
  - sample type
  - study / site / lab
  - receiving date
  - brought by
  - subject / sample / barcode identifiers
  - initial metadata JSON
  - first QC decision + notes
- rejected samples end immediately by creating a `ReceivingDiscrepancy`
- accepted samples continue into:
  - step 2: additional configured metadata fields
  - step 3: configured storage fields

Those dynamic steps are driven by the published sample-type metadata binding. Schema fields now expose a formbuilder-compatible field description in the metadata API, and the operator wizard uses a repository-native renderer so the controls stay aligned with the shared portal shell instead of introducing a separate frontend stack.

The same launchpad-versus-task-page pattern now extends to reference, metadata, and storage/inventory setup:

- `/lims/reference/` stays an overview/launchpad for labs, studies, sites, and geography sync status
- `/lims/reference/labs/create/`
- `/lims/reference/studies/create/`
- `/lims/reference/sites/create/`
- `/lims/reference/address-sync/`
- `/lims/metadata/` stays an overview/launchpad for vocabularies, fields, schemas, and bindings
- `/lims/metadata/vocabularies/create/`
- `/lims/metadata/fields/create/`
- `/lims/metadata/schemas/create/`
- `/lims/metadata/bindings/create/`
- `/lims/metadata/versions/publish/`
- `/lims/storage/` stays an overview/launchpad for storage hierarchy, placements, materials, lots, and ledger activity
- `/lims/storage/locations/create/`
- `/lims/storage/placements/create/`
- `/lims/storage/materials/create/`
- `/lims/storage/lots/create/`
- `/lims/storage/transactions/create/`

This keeps operator/admin pages closer to the CRUD cookbook direction: summary pages remain navigational, while each input page exposes one focused task with one primary submit action.

For Tanzania geography sync, a run may still enter `paused` between slices because it respects `request_budget` and `throttle_seconds`, but worker tasks now auto-resume paused runs until the queue is exhausted. Operators should not need a separate "resume" button for normal incremental progress.

## Batch and plate management

The current batch-management slice standardizes the first processing and worksheet primitives on top of the biospecimen aggregate:

- `PlateLayoutTemplate`
- `ProcessingBatch`
- `BatchPlate`
- `BatchPlateAssignment`

Current conventions:

- seeded layout templates provide tenant-local defaults for `96-well` and `384-well` plates
- processing batches stay tenant-aware through the same `sample_type`, `study`, `site`, and `lab` references used elsewhere in LIMS
- each plate assignment binds one biospecimen to one validated position and normalized well label
- duplicate specimen assignment within the same batch is rejected explicitly instead of being silently overwritten
- worksheet generation reuses the existing printing job stack and preview renderers rather than introducing a parallel document subsystem

The first API surface is exposed under:

- `/api/v1/lims/plate-layouts`
- `/api/v1/lims/processing-batches`
- `/api/v1/lims/processing-batches/<batch_id>`
- `/api/v1/lims/processing-batches/<batch_id>/transition`
- `/api/v1/lims/processing-batches/<batch_id>/worksheet`
- `/api/v1/lims/processing-batches/<batch_id>/worksheet-print-job`

Worksheet print jobs default to the shared `a4/batch-rows` template and `pdf` output so operators can generate A4-ready plate worksheets while still benefiting from the standard print preview metadata produced by the platform printing service.

The companion page at `/lims/processing/` provides a first admin-style batch workspace with layout visibility, batch creation, and worksheet print-job triggers.

## Storage and non-sample inventory direction

The current storage/inventory slice now treats two related concerns explicitly:

- sample storage and movement history for biospecimens, aliquots, pools, and derived artifacts
- non-sample inventory for lab materials and consumables such as reagents, tubes, kits, media, and labels

For non-sample inventory, the target model should remain relational and tenant-scoped, covering:

- material/catalog identity
- lot or batch tracking
- unit-of-measure aware stock quantities
- storage location and placement
- receipt, adjustment, reservation, transfer, usage, expiry, and disposal transactions
- workflow/task linkage when a consumable is used during execution

The admin-style HTML surface now mirrors those concerns through `/lims/storage/` plus dedicated task pages for location creation, specimen placement, material setup, lot receipt, and stock-ledger transactions. Like receiving/reference/metadata, the launchpad stays navigational while each child page keeps one primary submit action tied to the existing JSON APIs.

## Geography import and Tanzania sync

Address metadata ingestion is designed to be polite and resumable, with Tanzania currently acting as the first concrete source:

- source: `https://www.tanzaniapostcode.com/`
- imported hierarchy target: `country -> region -> district -> ward -> street -> postcode`
- execution: Celery task in `src/lims/tasks.py`
- persisted checkpoint/state: `TanzaniaAddressSyncRun`

Guardrails:

- each run processes a bounded number of pages (`request_budget`)
- the task persists a queue/checkpoint so later invocations can resume
- `next_not_before_at` enforces a minimum delay between page fetches
- failures are surfaced on the sync run instead of silently dropped

This gives Mtafiti a path to periodic refreshes via Celery Beat or another scheduler without hammering the upstream postcode service, while leaving room for additional country-specific importers to populate the same generalized geography model later.

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
