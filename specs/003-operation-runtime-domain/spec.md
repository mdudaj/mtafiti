# Feature Specification: Operation runtime domain

**Feature ID**: `003-operation-runtime-domain`  
**Execution Branch**: `docs/operation-runtime-domain`  
**Created**: 2026-03-19  
**Status**: Draft  
**Input**: GitHub issue `#108` "Design operation runtime domain"

## Repository Context *(mandatory)*

- **Service area**: shared `lims` / future `edcs` runtime foundation
- **Affected code paths**: `src/core/models.py`, `src/core/views.py`, `src/lims/models.py`, future shared operation/runtime app(s), `docs/lab-lims.md`, `docs/workflow-ui.md`
- **Related design docs**: `specs/002-operation-driven-lims-edcs-foundation/spec.md`, `specs/002-operation-driven-lims-edcs-foundation/plan.md`, `docs/lab-lims.md`, `docs/workflow-ui.md`
- **Prior checkpoints**: `022-architecture-spec-and-skills.md`, `017-accession-wizard-and-metadata.md`, `016-preview-and-receiving-refactor.md`
- **Knowledge graph / skills evidence**: `viewflow-configurable-workflow-runtime-patterns`, `viewflow-governed-workflow-definition-patterns`, `viewflow-assignment-permission-patterns`
- **External API lookup needs**: verify final Viewflow `Process`/`Task` runtime mapping and approval/e-signature practices during implementation
- **Related issues / PRs**: parent issue `#107`, scoped issue `#108`, merged architecture PR `#112`

## Problem Statement

The merged foundation spec establishes that operations, form packages, workflow templates, and runtime execution must be distinct. The repository already has lightweight `WorkflowDefinition`, `WorkflowRun`, and `WorkflowTask` models plus LIMS accessioning and biospecimen records, but it does not yet define the governed operation runtime model that ties together:

- versioned operation configuration
- activation and supersession lifecycle
- runtime execution state
- task-level submissions and approvals
- auditable material/specimen usage
- in-flight behavior when a newer operation version is published

Without this slice, implementation risks either overloading the generic `core` workflow scaffold or embedding LIMS-specific runtime assumptions that EDCS cannot reuse.

## Goals

- Define first-class `OperationDefinition` and `OperationVersion` semantics for shared LIMS/EDCS use.
- Define runtime entities that preserve immutable references to the exact operation, workflow, and form versions used for execution.
- Define approval, signature, audit, and material-usage records as explicit governed runtime concepts.
- Define in-flight version behavior so published updates do not silently mutate active runs.
- Map the new domain cleanly onto current repository primitives and identify what is reusable versus transitional.

## Non-Goals

- Full implementation of the operation runtime in this slice
- Detailed ODM/XLSX artifact structure for form packages
- Detailed workflow-builder node editor semantics
- Full 21 CFR Part 11 compliance pack in the first implementation increment
- Replacing Viewflow or the current tenant-aware Django runtime boundary

## Architectural Position

This slice refines the runtime half of the operation-driven foundation from `002-operation-driven-lims-edcs-foundation`.

Key position statements:

- `WorkflowDefinition` / `WorkflowRun` / `WorkflowTask` in `src/core/` are useful repository evidence, but they are **too generic and too narrow** to serve as the final governed operation runtime.
- The future shared runtime should preserve the good parts of that scaffold:
  - explicit run/task records
  - auditable status transitions
  - role-gated transition endpoints
- The future shared runtime must add missing governed concepts:
  - operation identity and version freeze
  - runtime linkage to authored form/workflow versions
  - submission records per task or form segment
  - approval/signature semantics with version context
  - material/specimen usage traceability
  - in-flight version compatibility rules

## Repository Evidence

### Existing reusable primitives

- `src/core/models.py` already demonstrates the repo preference for explicit runtime records via `WorkflowRun` and `WorkflowTask`.
- `src/core/views.py` already publishes workflow run events and audit events for run creation and transitions.
- `docs/workflow-ui.md` already anchors the platform on Viewflow and server-rendered operational UI.
- `src/lims/models.py` already provides biospecimen, aliquot, pool, accessioning manifest, receiving event, and discrepancy models that the runtime layer can reference instead of duplicating material state.

### Current gaps

- `WorkflowDefinition` is not versioned in the governed sense needed for operations.
- `WorkflowRun` does not freeze authored form/workflow versions or operation version context.
- `WorkflowTask` is too small for node identity, outcome capture, assignment history, approvals, or task-scoped submissions.
- The current workflow API is suited to governance/demo lifecycle transitions, not operation execution across intake, QC, storage, review, and EDCS-style capture tasks.
- Material/specimen consumption and produced artifacts are not modeled as first-class runtime links.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Govern operation versions independently of runtime (Priority: P1)

As a platform administrator, I want operation definitions and versions to be explicit and immutable once published so active runs stay bound to the exact approved design.

**Independent Test**: Create `sample-accession` definition version `1.0`, publish it, start runs against it, then create version `1.1` and confirm the original runs remain attached to `1.0`.

**Acceptance Scenarios**:

1. **Given** an operation definition exists, **When** a draft version is published, **Then** the published version becomes immutable and is eligible for activation.
2. **Given** an operation version is active, **When** a newer version is published, **Then** the newer version does not silently mutate existing runs.
3. **Given** a tenant uses the shared foundation, **When** they list operation versions, **Then** only tenant-scoped versions and allowed module context are visible.

---

### User Story 2 - Execute runs with explicit task and submission records (Priority: P1)

As an operator, I want each operation run and task run to preserve its own state, assignee, and captured submission context so execution is reviewable and resumable.

**Independent Test**: Start a sample accession run, progress through intake and QC task runs, save captured data as task submissions, and verify each runtime record remains queryable with status history and version references.

**Acceptance Scenarios**:

1. **Given** a published operation version is activated, **When** an operator starts a run, **Then** the system creates an `OperationRun` bound to the exact operation/workflow/form versions used.
2. **Given** the run advances to a task, **When** the task is created, **Then** the system records task type, node/template reference, assignee context, timestamps, and status separately from the overall run.
3. **Given** a task captures metadata, **When** an operator saves or submits data, **Then** the system stores a version-aware submission record linked to the task run.

---

### User Story 3 - Record approvals, signatures, and audit evidence (Priority: P1)

As a QA reviewer, I want approvals and signatures to be explicit runtime records with audit linkage so governed review is traceable.

**Independent Test**: Complete a QC review task requiring sign-off and verify the resulting approval record stores signer, role, meaning, timestamp, and the authored version context being signed.

**Acceptance Scenarios**:

1. **Given** a task requires approval, **When** an authorized reviewer signs it, **Then** the runtime stores an `ApprovalRecord` linked to the task run and operation run.
2. **Given** a task or run changes state, **When** the transition occurs, **Then** the audit/event stream includes actor, prior state, resulting state, rationale, and correlation data.
3. **Given** a versioned operation is later superseded, **When** reviewers inspect historical records, **Then** they can still see which exact version was approved and executed.

---

### User Story 4 - Trace specimen volume and material usage through runtime (Priority: P2)

As a laboratory manager, I want task execution to reference consumed and produced specimens, their quantity/volume effects, and the non-sample materials used so chain-of-custody and inventory remain explicit.

**Independent Test**: During sample accession or downstream processing, record an aliquot consumption event and a consumable usage event, then verify the runtime links the source biospecimen, resulting artifact, task run, quantity/volume semantics, and inventory usage semantics.

**Acceptance Scenarios**:

1. **Given** a task consumes a biospecimen, aliquot, or pool member, **When** the task is completed, **Then** a runtime-linked usage record links the action to the existing LIMS artifact records and records the governed quantity or volume effect.
2. **Given** a task produces a derivative or storage placement artifact, **When** the task completes, **Then** the runtime can reference the produced artifact without duplicating the source domain model and can explain the resulting quantity/volume state.
3. **Given** a task uses reagents, tubes, kits, or other consumables, **When** the task completes, **Then** the runtime can link that usage to inventory transactions instead of hiding it in free-text metadata only.
4. **Given** a discrepancy or rejection occurs, **When** runtime history is reviewed, **Then** material usage, quantity effects, and decision records remain correlated.

---

### User Story 5 - Reuse the same runtime core for EDCS (Priority: P2)

As a platform architect, I want the runtime model to serve both LIMS and EDCS so module-specific policies do not force separate engines.

**Independent Test**: Compare a LIMS accession run and a future EDCS visit/CRF run and confirm both can use the same `OperationRun`, `TaskRun`, `SubmissionRecord`, and `ApprovalRecord` structures while pointing at different subject and artifact references.

**Acceptance Scenarios**:

1. **Given** EDCS later reuses the foundation, **When** a visit workflow is executed, **Then** runtime entities remain compatible without requiring LIMS-only fields.
2. **Given** LIMS and EDCS enforce different roles, **When** runtime permissions are evaluated, **Then** role mapping can vary by module while the runtime record structure stays shared.

## Edge Cases

- What happens to runs that are still `draft` or `in_progress` when an operation version is superseded?
- How are partially completed task runs handled when a run is cancelled, short-circuited, or rejected?
- Can a task have multiple saved drafts before a final submitted capture record?
- How are approvals invalidated or preserved if a task is reopened under controlled override rules?
- How should the runtime represent tasks that render only a subset of a form package version?
- How should material usage be recorded when a task consumes multiple aliquots or pool members and produces one derived artifact?
- How should partial sample-volume reservations versus finalized consumption be represented for long-running workflows?
- How should runtime capture distinguish sample-artifact usage from non-sample inventory/consumable usage while preserving one coherent audit trail?
- How should subject context differ between LIMS specimens/batches and EDCS participants/visits without splitting the runtime model?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST model a first-class `OperationDefinition` as the stable identity of a governed activity.
- **FR-002**: The system MUST model `OperationVersion` records with draft/published/retired or equivalent lifecycle states and immutable published content.
- **FR-003**: The system MUST allow an operation version to reference SOP metadata, module scope, and tenant scope.
- **FR-004**: The system MUST allow only approved/published operation versions to be activated for runtime use.
- **FR-005**: The system MUST create `OperationRun` records bound immutably to the exact operation version, workflow template version, and form package version set used at start time.
- **FR-006**: The system MUST model `TaskRun` records separately from `OperationRun` records, including node/template reference, assignee context, status, timestamps, and outcome summary.
- **FR-007**: The system MUST model `SubmissionRecord` records for task-level or form-segment capture without mutating the authored versioned form definitions.
- **FR-008**: The system MUST support save/submit/finalize or equivalent capture lifecycle states for runtime submissions.
- **FR-009**: The system MUST model `ApprovalRecord` records as explicit runtime entities linked to operation runs and/or task runs.
- **FR-010**: The system MUST store approval/signature meaning, actor identity, actor role context, timestamp, and the authored version context being approved.
- **FR-011**: The system MUST emit audit/event records for operation and task lifecycle transitions, approvals, overrides, and significant capture actions.
- **FR-012**: The system MUST support correlation between audit events and runtime records through stable identifiers and correlation IDs.
- **FR-013**: The system MUST model `MaterialUsageRecord` records that reference existing LIMS artifact entities such as biospecimens, aliquots, pools, manifests, or derived artifacts instead of duplicating them.
- **FR-014**: The runtime model MUST support both consumed and produced artifact linkage for a task run.
- **FR-015**: The runtime model MUST support conditional short-circuit completion, rejection, cancellation, pause/resume, and controlled termination semantics.
- **FR-016**: The system MUST preserve in-flight runs on their original bound version set when newer operation versions are published or activated.
- **FR-017**: The system MUST define controlled migration rules for draft or not-yet-started runs when an operation version is superseded.
- **FR-018**: The system MUST support module-specific subject references without hard-coding the runtime model exclusively to LIMS specimens or EDCS visits.
- **FR-019**: The runtime model MUST support role-gated assignment, execution, review, and approval actions consistent with tenant-aware permission checks.
- **FR-020**: The system MUST remain compatible with a Viewflow-style runtime where orchestration state and task state are explicit and not hidden in free-form payloads.
- **FR-021**: Runtime capture MUST remain backed by relational tenant-scoped models; graph-style knowledge artifacts may describe the system but MUST NOT replace runtime persistence or audit requirements.
- **FR-022**: Workflow task submissions MUST be able to project governed values into domain models while still preserving the original submission/audit record for historical replay.
- **FR-023**: For LIMS workflows, sample/biospecimen records and their derivatives MUST remain the primary operational artifacts referenced by runtime tasks.
- **FR-024**: The runtime model MUST support explicit sample quantity/volume acquisition, derivation, reservation, and consumption records so workflow execution becomes the source of truth for sample usage history.
- **FR-025**: The runtime model MUST support linkage from task execution to non-sample lab inventory transactions for materials and consumables such as reagents, tubes, kits, and labels.

### Non-Functional Requirements

- **NFR-001**: Runtime lookups for active work queues MUST support efficient filtering by tenant, module, status, assignee, and created/updated timestamps.
- **NFR-002**: Historical execution records MUST remain renderable even after newer operation or form versions are published.
- **NFR-003**: Auditability MUST favor append-only or event-shaped history for significant runtime actions rather than silent in-place mutation.

### Key Entities *(include if feature involves data)*

- **OperationDefinition**: Stable identity for an activity such as Sample Accession or Visit Data Capture.
- **OperationVersion**: Tenant-scoped authored revision with SOP linkage, module scope, status, and activation lifecycle.
- **OperationRun**: Runtime execution of one published operation version against a subject or artifact context.
- **TaskRun**: Runtime execution of a workflow node or task within an operation run.
- **SubmissionRecord**: Captured runtime data linked to a task run and the exact versioned form context used.
- **ApprovalRecord**: Sign-off or review artifact linked to a run or task run with signer and meaning metadata.
- **MaterialUsageRecord**: Runtime linkage between a task and consumed/produced domain artifacts.
- **RuntimeVersionBinding**: Immutable frozen references from a run to the operation/workflow/form versions in force when execution started.

## Proposed Mapping to Current Repository

### Reuse

- Reuse the current explicit run/task shape from `WorkflowRun` and `WorkflowTask` as conceptual prior art.
- Reuse the current event publication and audit publication conventions from `src/core/views.py`.
- Reuse existing LIMS biospecimen, accessioning, receiving, and pool models as referenced artifact domains.

### Redefine or replace

- `WorkflowDefinition` should not become the final operation definition model; it is too generic and unversioned.
- `WorkflowRun` and `WorkflowTask` should be treated as transitional scaffolding or adapted into richer shared runtime entities.
- Free-form `payload` blobs should not be the only storage for governed runtime capture and approval context.

### Likely implementation layering

- `operation_config`: operation definitions and versions
- `workflow_config`: approved workflow template versions
- `form_engine`: approved form package versions
- `workflow_runtime` or shared operation runtime app: runs, task runs, submissions, approvals, material usage

## Success Criteria *(mandatory)*

- **SC-001**: The spec clearly distinguishes configuration-time operation/version records from runtime execution records.
- **SC-002**: The spec defines an immutable version-freeze contract for active runs.
- **SC-003**: The spec explains how task submissions, approvals, and audit events relate without collapsing them into one payload field.
- **SC-004**: The spec shows how runtime records reuse existing LIMS artifact domains for specimen/material traceability.
- **SC-005**: The spec is implementation-ready enough to drive a dedicated runtime-domain issue or PR slice.

## Delivery Mapping *(mandatory)*

- **Issue title**: Design operation runtime domain
- **Issue reference**: `#108`
- **Parent issue**: `#107`
- **Issue generation command**: `./.venv/bin/python .github/scripts/spec_kit_workflow.py issue-body specs/003-operation-runtime-domain`
- **PR generation command**: `./.venv/bin/python .github/scripts/spec_kit_workflow.py pr-body specs/003-operation-runtime-domain --issue-number 108`
- **Branch naming**: `docs/operation-runtime-domain`
