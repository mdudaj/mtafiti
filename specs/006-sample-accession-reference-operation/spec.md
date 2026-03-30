# Feature Specification: Sample Accession reference operation

**Feature ID**: `006-sample-accession-reference-operation`  
**Execution Branch**: `docs/sample-accession-reference-operation`  
**Created**: 2026-03-19  
**Status**: Draft  
**Input**: GitHub issue `#111` "Define Sample Accession as reference operation" plus the merged operation, runtime, ODM-engine, and workflow-builder foundation slices.

## Repository Context *(mandatory)*

- **Service area**: `lims` reference operation on the LIMS-specific operation foundation, with shared form-engine standards remaining available to future `edcs` work
- **Affected code paths**: `src/lims/models.py`, `src/lims/services.py`, `src/lims/views.py`, `docs/lab-lims.md`, future LIMS operation/workflow apps, shared form-engine app(s)
- **Related design docs**: `specs/002-operation-driven-lims-edcs-foundation/spec.md`, `specs/003-operation-runtime-domain/spec.md`, `specs/004-odm-form-engine-foundation/spec.md`, `specs/005-workflow-builder-foundation/spec.md`, `docs/lab-lims.md`
- **Prior checkpoints**: `022-architecture-spec-and-skills.md`, `019-reference-ux-and-routing.md`, `017-accession-wizard-and-metadata.md`, `016-preview-and-receiving-refactor.md`
- **Knowledge graph / skills evidence**: `openclinica-odm-form-engine-patterns`, `viewflow-configurable-metadata-forms`, `viewflow-configurable-workflow-runtime-patterns`, `viewflow-assignment-permission-patterns`
- **External API lookup needs**: verify implementation-time ODM/OpenClinica section/group conventions and Viewflow runtime compilation details via Context Hub or curated local skills
- **Related issues / PRs**: parent issue `#107`, scoped issues `#108`, `#109`, `#110`, current issue `#111`

## Problem Statement

The architecture foundation now defines:

- versioned operations
- a separate ODM/OpenClinica-style form compiler
- a bounded workflow-builder layer
- a governed runtime domain

What is still missing is a concrete reference operation proving those abstractions end-to-end.

The repository already has practical accessioning behavior:

- single-sample intake
- batch manifest intake
- EDC-linked intake
- first QC decision (`accept` or `reject`)
- accepted path to initial storage logging
- rejected path to discrepancy capture

But that behavior still lives in a transitional receiving-oriented slice. It does not yet define Sample Accession as a fully governed operation version with explicit task bindings, runtime records, and compiler-owned form package references.

Without this slice, the architecture remains plausible but not yet anchored to one canonical operational example that future LIMS implementation work can follow.

## Goals

- Define Sample Accession as the first fully described operation on the LIMS-specific operation foundation.
- Prove how one published operation version binds together:
  - operation identity and SOP context
  - compiler-owned form package outputs
  - workflow-template/node definitions
  - runtime run/task/submission/approval/material-usage records
- Define the canonical accession path from intake through QC to either storage logging or rejection and disposition closure.
- Map current receiving APIs and screens into the future governed operation model without discarding already useful operator behavior.
- Provide an implementation-ready reference slice that future operations in `lims` can imitate while preserving alignment with the shared form-engine standard.

## Non-Goals

- Implementing the full Sample Accession runtime in this specification slice
- Defining every downstream laboratory step after accession (sorting, extraction, pooling, analysis, archive)
- Building a generalized operation designer UI in this slice
- Replacing the current receiving endpoints before the governed operation runtime exists
- Finalizing all future EDCS reference operations

## Architectural Position

Sample Accession is the first **reference operation**, not a one-off workflow exception.

It should demonstrate the layered contracts already established:

1. **Operation layer**
   - `OperationDefinition(sample-accession)`
   - immutable published `OperationVersion`
   - SOP/version linkage
2. **ODM engine layer**
   - compiled published form package version(s)
   - stable package/section/group/item identifiers
   - validation and export provenance owned by the compiler
3. **Workflow builder layer**
   - bounded task graph for accession
   - task capture bindings to compiler-owned identifiers
   - assignment, permission, and approval metadata
4. **Runtime layer**
   - `OperationRun`, `TaskRun`, `SubmissionRecord`, `ApprovalRecord`, `MaterialUsageRecord`
   - immutable version freeze for each started accession run
5. **UI / orchestration layer**
   - Viewflow-compatible execution and Django-rendered operator pages
   - launchpad and dedicated task pages as consumers of compiled/runtime contracts

This slice therefore becomes the concrete proof that:

- the ODM engine is separate from orchestration/UI
- the workflow builder is separate from both compiler and runtime
- runtime records are separate from authored definitions
- the current receiving UX is a transitional expression of a broader governed operation model

## Reference Operation Overview

### Stable identity

- **Operation code**: `sample-accession`
- **Operation name**: `Sample Accession`
- **Module scope**: `lims`
- **Primary purpose**: receive or register incoming biospecimens into governed custody, capture accession metadata, record the first QC decision, and either place accepted material into initial storage or close the accession through discrepancy/rejection handling

### Supported intake modes

All of the following are entry modes into the same governed operation:

- **Single receipt**: bench or scan-oriented direct accession of one sample
- **Batch receipt**: manifest-driven intake of many expected samples
- **EDC-linked receipt**: import-anchored intake where external identifiers and expected metadata are pulled from an upstream EDC context

These modes differ in how the run is initiated and how intake data is prefilled, but they converge on the same operation semantics, task graph, and runtime evidence model.

## Canonical Workflow Shape

The reference workflow for a published `Sample Accession` version is:

`Start -> Intake Capture -> QC Decision -> (Accepted -> Initial Storage Logging -> End) | (Rejected -> Discrepancy / Disposition Closure -> End)`

### Node intent

- **Start**
  - create the accession run in the correct tenant and module context
  - bind the run to the exact published operation/workflow/form versions
- **Intake Capture**
  - capture source, participant/study/site/lab, container, barcode, expected sample type, receipt envelope, and initial provenance metadata
  - optionally prefill values from manifest or EDC import sources
- **QC Decision**
  - record first-pass accept/reject decision, condition notes, reviewer identity, and any gating observations
- **Initial Storage Logging**
  - for accepted samples only, capture initial storage placement and receipt-complete state
- **Discrepancy / Disposition Closure**
  - for rejected samples only, capture discrepancy code, rejection reason, disposition notes, and closure semantics
- **End**
  - end the operation with an explicit accepted or rejected terminal outcome

## Compiler-owned Form Package Direction

The reference operation should prove task-level capture by binding to compiler-owned published outputs, not by inventing fields in workflow or UI code.

Sample Accession is also the mandatory first governed specimen activity in LIMS. Downstream specimen-handling operations should assume accession evidence already exists and should not bypass it with parallel intake paths.

### Preferred package shape

The initial reference design should use one primary published package family such as `sample-accession-package`, with task-specific bindings to sections and items.

Suggested section families:

- **Receipt Envelope**
  - receipt date/time
  - brought by / courier / collector context
  - manifest or external import identifiers
- **Sample Identity & Context**
  - sample type
  - study / site / lab
  - participant / subject / visit / external identifiers
  - barcode / local accession identifiers
- **Condition & Intake Metadata**
  - observed condition
  - temperature/transport notes
  - operator observations
- **QC Decision**
  - accept/reject outcome
  - QC notes
  - reviewer identity / timestamp context
- **Storage Placement**
  - facility / room / freezer / rack / box / position or equivalent interim storage references
  - storage-condition notes
- **Outcome / Disposition Log**
  - terminal outcome classification
  - disposition action
  - disposition notes
- **Discrepancy & Rejection**
  - discrepancy code
  - rejection reason
  - disposition comments

### Binding expectations

- **Intake Capture** binds receipt, identity/context, and condition/intake sections.
- **QC Decision** binds only the QC decision section plus any decision-driving items needed for routing.
- **Initial Storage Logging** binds storage-placement items and any storage-log fields needed to complete governed custody logging.
- **Discrepancy / Disposition Closure** binds discrepancy, rejection, and disposition-log items.

This proves the workflow-builder contract that tasks consume published package/section/group/item outputs rather than duplicating form definitions.

All accession capture in this slice follows one rule: metadata, outcomes, storage-log entries, and disposition-log entries are recorded through task-bound package submissions first, then projected into biospecimen, receiving, discrepancy, storage, and related domain models as governed relational consequences.

## Runtime Semantics

### Operation run creation

Each accession begins as an `OperationRun` that freezes:

- published `OperationVersion`
- published `WorkflowTemplateVersion`
- published `FormPackageVersion` set
- tenant scope
- module scope
- subject/material context known at start
- origin mode (`single`, `batch`, or `edc-import`)

### Task runs

The runtime should create task runs for:

- `intake_capture`
- `qc_decision`
- `initial_storage_logging` when QC accepts
- `disposition_closure` when QC rejects

Each `TaskRun` should preserve:

- node/template reference
- assignee/role context
- status and timestamps
- outcome summary
- linked `SubmissionRecord` versions
- audit/event correlations

### Material and artifact linkage

The operation should explicitly relate runtime records to current LIMS aggregates rather than hiding those links in JSON:

- expected or created `Biospecimen`
- manifest and manifest item, when batch intake is used
- `ReceivingEvent`
- `ReceivingDiscrepancy` for rejection path
- future storage artifacts/placements

`MaterialUsageRecord` semantics for accession are lighter than downstream processing, but the operation should still record:

- the specimen entering governed custody
- any identifier normalization or binding to an existing record
- resulting storage-placement artifact references for accepted samples

## Current-to-target Mapping

### Current repository behavior that remains valid

- `/lims/receiving/` acting as a launchpad is aligned with the future operation launch surface
- `/lims/receiving/single/`, `/lims/receiving/batch/`, and `/lims/receiving/edc-import/` already map well to distinct accession initiation modes
- first-pass QC decision and conditional storage/discrepancy handling already reflect the intended branching behavior
- current manifest, receiving event, discrepancy, and biospecimen models provide transitional runtime evidence and domain references

### What must be reinterpreted

- current receiving endpoints should become adapters or transitional entrypoints into the governed `sample-accession` runtime rather than the final domain boundary
- current metadata-schema bindings are useful precedent, but the target binding contract is to compiler-owned package versions and section/item identifiers
- current receipt metadata JSON should become structured runtime submissions tied to task runs

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Publish Sample Accession as a governed operation version (Priority: P1)

As a laboratory administrator, I want Sample Accession defined as a versioned operation with SOP context so receiving behavior becomes governed and reviewable.

**Independent Test**: Publish `sample-accession` version `1.0` with linked workflow template and compiled form package bindings, then confirm future updates require a new draft/published version rather than mutating the active definition.

**Acceptance Scenarios**:

1. **Given** a tenant needs governed sample intake, **When** they publish `sample-accession` version `1.0`, **Then** the system stores operation identity, SOP linkage, module scope, and version lifecycle explicitly.
2. **Given** the accession definition later changes, **When** a new revision is authored, **Then** the prior published version remains immutable.
3. **Given** multiple tenants use the platform, **When** one tenant publishes Sample Accession, **Then** only that tenant's definition is active unless a future shared-library model is introduced.

---

### User Story 2 - Start accession runs from single, batch, or EDC intake (Priority: P1)

As an operator, I want different intake modes to create the same governed accession run so operational semantics stay consistent.

**Independent Test**: Start one accession from `/lims/receiving/single/`, one from a manifest, and one from EDC-linked import, then verify all three create runs of the same `sample-accession` operation version with different origin metadata.

**Acceptance Scenarios**:

1. **Given** an operator starts a direct bench receipt, **When** they submit intake data, **Then** the system creates a `sample-accession` run with origin mode `single`.
2. **Given** an operator processes a manifest item, **When** they start accession from that item, **Then** the run links manifest and manifest-item context without changing the operation definition.
3. **Given** an operator uses an EDC-linked intake, **When** external identifiers prefill the form, **Then** the run still uses the same governed operation and task graph as other modes.

---

### User Story 3 - Route accepted and rejected samples through explicit task outcomes (Priority: P1)

As a lab operator, I want QC to control whether the sample proceeds to storage or closes as a rejection so the operation matches real receiving practice.

**Independent Test**: Complete one accession with QC `accept` and confirm the storage task is created; complete another with QC `reject` and confirm the storage task is skipped and disposition closure becomes the terminal path.

**Acceptance Scenarios**:

1. **Given** intake capture is complete, **When** QC records `accept`, **Then** the runtime creates `initial_storage_logging` and does not create disposition closure.
2. **Given** intake capture is complete, **When** QC records `reject`, **Then** the runtime creates discrepancy and disposition closure and short-circuits storage logging.
3. **Given** the run reaches a terminal state, **When** history is reviewed, **Then** it is clear whether the accession finished as accepted or rejected.

---

### User Story 4 - Preserve auditable accession evidence across task runs (Priority: P1)

As a QA reviewer, I want Sample Accession to generate task-level submissions, audit evidence, and domain links so custody and review remain traceable.

**Independent Test**: Run one accepted and one rejected accession, then inspect run history to confirm task runs, submissions, event history, biospecimen links, and storage or discrepancy references are all preserved.

**Acceptance Scenarios**:

1. **Given** an intake task saves data, **When** the submission is recorded, **Then** it is stored as a structured task-linked submission against the exact published form version used.
2. **Given** QC or closure changes run progression, **When** those actions complete, **Then** audit/event records capture actor, prior state, resulting state, and rationale.
3. **Given** the accession binds or creates a specimen and reaches storage or disposition closure, **When** history is reviewed, **Then** specimen/material references remain explicit.

---

### User Story 5 - Use Sample Accession as the implementation template for later operations (Priority: P2)

As a platform architect, I want Sample Accession to be specific enough that later LIMS operations can follow its pattern while EDCS reuses only the shared form-engine standard instead of inventing incompatible models.

**Independent Test**: Derive a checklist for a later operation such as sample sorting or visit data capture and confirm the same operation/form/workflow/runtime layers can be reused.

**Acceptance Scenarios**:

1. **Given** a later LIMS operation is designed, **When** the team follows this reference slice, **Then** it can reuse the same operation/version, package binding, workflow template, and runtime patterns.
2. **Given** EDCS later defines a visit intake operation, **When** it reuses the same contracts, **Then** only module-specific subject and UI policies differ.

## Edge Cases

- How should a batch manifest item that is partially prefilled but not yet started map into a not-yet-started accession run?
- How should duplicate barcode or external identifier detection influence task progression versus compiler validation?
- Can QC accept a sample with warning-level issues that still require discrepancy notes but do not block storage?
- How should storage logging behave if the storage hierarchy domain is not yet fully implemented and only interim placement metadata is available?
- How should accession runs represent rescinded or reopened QC decisions under controlled override rules?
- How should one accession run behave when multiple physical containers map to one logical expected sample?
- How should EDC-linked intake preserve upstream provenance while still using the same canonical compiled package and workflow bindings?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST model Sample Accession as a first-class `OperationDefinition` / `OperationVersion` reference operation under the LIMS-specific operation foundation.
- **FR-002**: Published Sample Accession versions MUST be immutable and require a new draft/published version for changes.
- **FR-003**: The reference operation MUST support single, batch, and EDC-linked initiation modes without changing the core operation semantics.
- **FR-004**: Each accession run MUST freeze the exact published operation, workflow-template, and form-package versions used at start time.
- **FR-005**: The reference workflow MUST include intake capture, QC decision, and terminal branching to either initial storage logging or rejection and disposition closure.
- **FR-006**: Task capture for Sample Accession MUST bind to compiler-owned published package/version/section/group/item outputs.
- **FR-007**: The intake task MUST support prefill or correlation data from manifest and EDC sources without changing the underlying compiled package semantics.
- **FR-008**: The QC task MUST produce an explicit accepted/rejected outcome usable by workflow branching.
- **FR-009**: Accepted accession runs MUST create or complete an initial storage-logging path before terminal completion.
- **FR-010**: Rejected accession runs MUST create explicit discrepancy and disposition-closure records and terminate without storage logging.
- **FR-011**: The runtime MUST create task-linked `SubmissionRecord` entries for accession capture rather than relying only on free-form receipt metadata JSON.
- **FR-012**: The runtime MUST emit auditable event history for run creation, task completion, branching decisions, storage completion, and disposition closure.
- **FR-013**: The runtime MUST link accession runs to existing LIMS aggregates including biospecimens, manifests, receiving events, and discrepancies where applicable.
- **FR-014**: The reference operation MUST remain tenant-scoped and module-scoped.
- **FR-015**: The specification MUST map current `/lims/receiving/*` task pages and APIs as transitional adapters or entrypoints into the future governed operation.
- **FR-016**: The reference operation MUST be specific enough to drive future implementation slicing for operation config, compiler bindings, runtime, and UI migration.
- **FR-017**: Sample Accession MUST act as the prerequisite governed operation for downstream specimen-handling activities unless an explicitly governed exceptional path is later defined.
- **FR-018**: Each Sample Accession version MUST include mandatory SOP context so execution is reviewable against an approved receiving procedure.
- **FR-019**: Metadata capture, outcome capture, storage-log capture, and disposition-log capture MUST be recorded through task-bound compiler-owned package submissions before projection into domain aggregates.
- **FR-020**: Each accession submission and resulting runtime decision MUST remain traceable to specimen or intake context, operation version, SOP version context, form package version, task/run, and actor.

### Non-Functional Requirements

- **NFR-001**: The reference operation design MUST stay deterministic enough that workflow, binding, and knowledge-graph artifacts remain stable in CI.
- **NFR-002**: Historical accession runs MUST remain renderable against the originally published version set even after newer accession versions exist.
- **NFR-003**: The current receiving UX SHOULD remain evolvable toward the governed runtime without requiring a disruptive frontend rewrite first.

### Key Entities *(include if feature involves data)*

- **SampleAccessionOperationDefinition**: Stable identity for the Sample Accession operation.
- **SampleAccessionOperationVersion**: Published or draft accession definition revision with SOP linkage.
- **AccessionWorkflowTemplateVersion**: Published bounded workflow topology for accession.
- **AccessionFormPackageVersion**: Compiler-owned published package version consumed by accession tasks.
- **AccessionRun**: `OperationRun` instance for a single, batch-item, or EDC-linked accession.
- **AccessionTaskRun**: `TaskRun` instance for intake, QC, storage, or disposition closure.
- **AccessionSubmissionRecord**: Task-linked structured capture for an accession step.
- **AccessionApprovalRecord**: Optional explicit sign-off artifact if QC or disposition closure requires formal approval.
- **AccessionMaterialUsageRecord**: Runtime linkage to biospecimen and resulting storage-placement artifacts.

## Proposed Implementation Slicing

1. **Operation configuration wiring**
   - define `sample-accession` operation definition/version fixtures or authored records
2. **Compiler binding contract**
   - define package/section/item identifiers used by accession tasks
3. **Workflow-template publication**
   - define bounded accession topology and branch rules
4. **Runtime adapter/migration**
   - map current receiving APIs and models into `OperationRun` / `TaskRun` / `SubmissionRecord` flow
5. **UI migration**
   - keep `/lims/receiving/` launchpad and task pages, but route them through governed runtime contracts

## Success Criteria *(mandatory)*

- **SC-001**: The spec describes Sample Accession end-to-end across operation, compiler, workflow, runtime, and UI layers.
- **SC-002**: The spec makes the accept/reject branch and conditional storage/rejection path explicit.
- **SC-003**: The spec clearly maps current receiving behavior into the future governed operation model instead of discarding it.
- **SC-004**: The spec proves task-level bindings to compiler-owned package outputs with one concrete reference operation.
- **SC-005**: The spec is implementation-ready enough to drive a dedicated issue/PR and later concrete backend/runtime work.
- **SC-006**: The spec makes Sample Accession explicit enough to serve as the governed prerequisite pattern for later specimen-handling operations.

## Delivery Mapping *(mandatory)*

- **Issue title**: Define Sample Accession as reference operation
- **Issue reference**: `#111`
- **Parent issue**: `#107`
- **Issue generation command**: `./.venv/bin/python .github/scripts/spec_kit_workflow.py issue-body specs/006-sample-accession-reference-operation`
- **PR generation command**: `./.venv/bin/python .github/scripts/spec_kit_workflow.py pr-body specs/006-sample-accession-reference-operation --issue-number 111`
- **Branch naming**: `docs/sample-accession-reference-operation`
