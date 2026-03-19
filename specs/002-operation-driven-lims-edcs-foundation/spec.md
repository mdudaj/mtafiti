# Feature Specification: Operation-driven LIMS/EDCS foundation

**Feature ID**: `002-operation-driven-lims-edcs-foundation`  
**Execution Branch**: `feat/operation-driven-lims-edcs-foundation`  
**Created**: 2026-03-19  
**Status**: Draft  
**Input**: User description: "Redefine LIMS architecture around configurable operations/activities, ODM-managed electronic forms, Viewflow workflow nodes/tasks, conditional rules, auditability, and shared reuse with EDCS."

## Repository Context *(mandatory)*

- **Service area**: shared `lims` / `edcs` architecture foundation
- **Affected code paths**: `src/lims/`, `src/core/models.py`, future `src/edcs/`, `docs/lab-lims.md`, `docs/edcs.md`, `docs/workflow-ui.md`
- **Related design docs**: `docs/lab-lims.md`, `docs/edcs.md`, `docs/workflow-ui.md`, `docs/metadata-versioning.md`, `docs/spec-kit-workflow.md`
- **Knowledge graph / skills evidence**: local skills include `viewflow-configurable-metadata-forms`, `viewflow-configurable-workflow-runtime-patterns`, `viewflow-assignment-permission-patterns`, and the broader Viewflow/django-material cookbook-derived skills
- **External API lookup needs**: during implementation, verify ODM/CDISC, Viewflow runtime constraints, and e-signature/audit patterns with Context Hub or curated local sources
- **Related issues / PRs**: none yet; this spec should become the source for the next architecture and implementation issue set

## Architectural Position

This specification **supersedes the current metadata-first framing as the primary LIMS architecture direction**. The merged metadata/vocabulary work remains valuable, but it should now be treated as a **transitional lower-level subsystem** that must be **redefined toward an ODM/OpenClinica-style form-package model** inside a broader operation-driven foundation used by both `lims` and `edcs`.

In practical terms:

- controlled vocabularies remain reusable foundation primitives
- the earlier versioned-form work is not the final target model; it should be evolved into OpenClinica-style governed form packages with sections, groups, items, stable identifiers, and ODM/XLSX artifacts
- workflow binding moves up a level from "bind a form to a target key" toward "bind forms and rules to tasks inside a versioned operation/workflow template"
- LIMS sample accession becomes the first reference operation proving the foundation
- EDCS should later reuse the same form/version/rule/audit core for study visits, CRFs, and submission/review flows

## Research Anchors

### OpenClinica-inspired form-engine findings

- OpenClinica treats forms/CRFs as **versioned definitions**, and changes that affect active forms create a **new version** rather than mutating the prior one in place.
- Authoring supports both a **visual designer** and a **spreadsheet template** path; the spreadsheet path remains important for advanced logic such as cascading selects, hard edit checks, and large choice sets.
- The form structure is not flat. It is organized around:
  - form/package metadata
  - sections/pages
  - item groups, including repeating groups
  - items/questions
  - choice lists
  - stable identifiers / OIDs for downstream import/export and interoperability
- ODM XML is best treated as an **interchange and artifact contract** for metadata/data portability, not necessarily as the only canonical persistence model for application runtime.
- Historical data remains tied to the original authored form version, so runtime submissions must always keep a durable reference to the exact version used.
- This means the current repository's versioned-form work should be regarded as an **intermediate foundation** rather than the final architecture; it needs to be reshaped to match package/section/group/item semantics and stable identifier behavior expected by ODM/OpenClinica-style systems.

### Viewflow-inspired workflow findings

- Viewflow expects explicit runtime state in `Process` and `Task` models, with `Flow` classes defining orchestration separately from business data.
- The practical workflow-builder target should be a **bounded node palette**, not an unlimited free-form designer. The relevant supported node family for this architecture is:
  - `Start`
  - `StartHandle`
  - `View`
  - `Function`
  - `Handle`
  - `If`
  - `Switch`
  - `Split`
  - `SplitFirst` where needed
  - `Join`
  - `End`
- Assignment and authorization should be declared in workflow definitions through node metadata such as `Assign(...)` and `Permission(...)`, rather than scattered across view code.
- Split/join and switch/if semantics should be first-class in the workflow template model because batch work, QC review, and conditional short-circuiting are central to LIMS/EDCS workflows.
- Flow registration and operator UI should align with `FlowAppViewset` / `Application` / `Site` patterns so the workflow runtime integrates cleanly with the future server-rendered shell.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Define a governed lab operation (Priority: P1)

As a laboratory administrator, I want to define a versioned operation with a name, SOP reference, purpose, and lifecycle so operational workflows are explicit, reviewable, and reusable.

**Why this priority**: The operation is the new top-level unit of configuration. Without it, forms and workflows remain disconnected building blocks.

**Independent Test**: An administrator can create an operation such as `sample-accession`, version it, link an SOP/version, mark it draft or published, and see that downstream workflow/form configuration attaches to that operation version rather than to ad hoc target keys.

**Acceptance Scenarios**:

1. **Given** an administrator wants to define `Sample Accession`, **When** they create an operation definition and its first version, **Then** the system stores operation identity, description, SOP linkage, and version lifecycle metadata.
2. **Given** an operation version is already published, **When** a new revision is needed, **Then** a new draft version can be created without mutating the published version.
3. **Given** multiple tenants use the platform, **When** one tenant defines an operation, **Then** the definition remains tenant-scoped unless an explicit future shared-library model is introduced.

---

### User Story 2 - Administer reusable electronic forms as standards-aware packages (Priority: P1)

As a form designer, I want to author and version electronic forms using ODM-compatible structures with downloadable XML/XLSX artifacts so the same form engine can serve LIMS and EDCS.

**Why this priority**: Forms are no longer generic metadata attachments; they become governed packages with standards-oriented import/export expectations.

**Independent Test**: A designer can create a form package, author a draft version, manage fields/questions and edit checks, publish the version, and export or import an ODM-aligned representation plus spreadsheet-designer representation.

**Acceptance Scenarios**:

1. **Given** a new operation form is needed, **When** a designer creates it, **Then** the form has identity metadata, version lifecycle, package structure, and artifacts rather than being just a loose schema binding.
2. **Given** a published form exists, **When** a designer downloads the definition, **Then** the system provides a machine-readable ODM/XML representation and a spreadsheet-friendly representation for governed change workflows.
3. **Given** a tenant later needs EDCS reuse, **When** the same form engine is used for a study visit form, **Then** the core versioning, field, rule, and export contracts remain the same even if the runtime context differs.

---

### User Story 3 - Design task-level workflows with conditional field capture (Priority: P1)

As a workflow designer, I want to define task/node templates for an operation and bind which form sections or fields are captured at each task so runtime execution follows a governed operational path.

**Why this priority**: The user's main architectural shift is from standalone forms toward workflows where each task captures specific metadata and branching depends on outcomes.

**Independent Test**: A designer can define a workflow template for `Sample Accession` with tasks such as intake, QC, and storage logging; the QC outcome can decide whether storage appears or the operation ends early.

**Acceptance Scenarios**:

1. **Given** an operation has multiple steps, **When** a workflow designer defines nodes and edges, **Then** each node can reference the form package or subset needed for that task.
2. **Given** a prior task records a rejection decision, **When** the process advances, **Then** downstream tasks configured as conditional on acceptance are skipped and the workflow ends correctly.
3. **Given** a task only needs a subset of form questions, **When** the node configuration is rendered, **Then** only the allowed fields or sections for that node are shown.

---

### User Story 4 - Execute operations with auditability, approvals, and signatures (Priority: P2)

As a QA officer or manager, I want operation execution to produce auditable task history, signatures/approvals where required, and traceable material usage so compliance and review workflows are trustworthy.

**Why this priority**: Audit and compliance are part of the user's target direction, but they depend on the operation/form/workflow foundation being explicit first.

**Independent Test**: During a reference accession workflow, task completion, QC outcomes, overrides, approvals, and specimen-material usage are recorded with actor, timestamp, prior state, resulting state, and rationale.

**Acceptance Scenarios**:

1. **Given** a task outcome changes workflow progression, **When** the task is completed, **Then** an immutable audit/event entry captures the decision and actor.
2. **Given** a task requires sign-off, **When** an authorized reviewer signs or approves it, **Then** the record stores the signer, meaning, timestamp, and signed version context.
3. **Given** a specimen aliquot or portion is consumed during a task, **When** the task is completed, **Then** the runtime record links the consumed material and resulting artifacts.

---

### User Story 5 - Reuse the same foundation for EDCS workflows (Priority: P2)

As a platform architect, I want LIMS and EDCS to share the same operation/form/workflow foundation so the system stays configurable and avoids parallel engines for closely related governed data-capture processes.

**Why this priority**: The user explicitly wants the form engine reusable for EDCS, so reuse is a design requirement rather than a possible future convenience.

**Independent Test**: The architecture can describe both a LIMS accession operation and an EDCS visit/CRF workflow using the same core entities with module-specific runtime policies layered on top.

**Acceptance Scenarios**:

1. **Given** EDCS later defines a visit workflow, **When** the foundation models are reused, **Then** operation definitions, form packages, task templates, and runtime records do not require a second incompatible engine.
2. **Given** LIMS and EDCS have different UI shells or permission bundles, **When** they use the shared foundation, **Then** shared entities stay consistent while module-specific navigation and policies remain separable.

## Edge Cases

- How are in-flight executions handled when an operation version or workflow template is superseded?
- Can a task render only part of a form version without duplicating the underlying field definitions?
- How are historical submissions rendered if a vocabulary item or form field is later retired?
- What is the initial compliance target: internal canonical model with ODM-compatible import/export, rather than raw ODM XML as the only persistence format?
- How are rule collisions handled when both form-level edit checks and workflow-level branching conditions depend on the same prior answers?
- How is tenant-safe search and API access enforced when reusable vocabularies or templates eventually become shareable libraries?
- What happens if a required approval/signature step is added in a newer operation version while older runs remain active?
- How are stable item/group/form identifiers preserved across versions so ODM/XML import-export and historical rendering stay lossless?
- How are very long choice lists or hierarchical choice filters represented without embedding huge enumerations directly in every task form payload?
- Which advanced logic belongs to form-level edit checks versus workflow-level routing, and how are the two evaluated in a deterministic order?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST model a first-class `Operation Definition` and `Operation Version` for governed activities such as sample accession, with name, code, description, version, status, and SOP linkage.
- **FR-002**: The system MUST support draft and published operation versions, and published versions MUST be immutable.
- **FR-003**: The system MUST support a reusable electronic form package model with version lifecycle and standards-aware metadata suitable for both LIMS and EDCS.
- **FR-004**: The system MUST support form import/export contracts for ODM/XML-compatible artifacts and spreadsheet-designer artifacts such as XLSX.
- **FR-005**: The system MUST model form packages with structure comparable to governed CRF systems: form/package metadata, sections/pages, item groups including repeating groups, items/questions, and controlled choices.
- **FR-006**: The system MUST allow form questions/fields, edit checks, vocabularies, and presentation hints to belong to a specific form version/package version.
- **FR-007**: The system MUST preserve stable identifiers for forms, sections, groups, and items so import/export and historical submission rendering remain lossless across versions.
- **FR-008**: The current merged versioned-form implementation MUST be treated as a migration starting point and redefined toward the governed ODM/OpenClinica-style package structure rather than preserved verbatim as the final model.
- **FR-009**: The system MUST allow workflow templates to be defined per operation version using Viewflow-compatible task/node and edge concepts.
- **FR-010**: The workflow-template model MUST compile only into a bounded supported node palette derived from Viewflow capabilities rather than unrestricted arbitrary graph semantics.
- **FR-011**: The system MUST allow each workflow node/task to declare which form package, sections, groups, or fields are captured at that step.
- **FR-012**: The system MUST support conditional branching and task visibility rules based on prior task outcomes or captured data.
- **FR-013**: The system MUST keep design-time workflow/template definitions separate from runtime `Process`/`Task`-style execution state.
- **FR-014**: The system MUST record operation execution as runtime records separate from design-time definitions.
- **FR-015**: The system MUST support audit trails for operation versioning, workflow progression, data capture, overrides, approvals, and configuration changes.
- **FR-016**: The system MUST support role-based access controls for design, execution, review, approval, and administrative actions, with object-level controls where needed.
- **FR-017**: The system MUST support signature/approval semantics as explicit workflow or task requirements, even if stricter Part 11 behavior is phased in later.
- **FR-018**: The system MUST support import/export and integration boundaries for EDC, instrument, and reporting workflows without tightly coupling runtime logic to a single external system.
- **FR-019**: The system MUST support material or specimen usage linkage from workflow tasks to resulting artifacts where applicable.
- **FR-020**: The system MUST preserve tenant isolation across operation definitions, form packages, workflow templates, vocabularies, runtime records, and analytics.

### Non-Goals

- Building a full drag-and-drop browser workflow designer in the first slice
- Implementing the entire EDCS module in this specification slice
- Replacing Viewflow with another workflow engine
- Achieving full 21 CFR Part 11 certification in the first implementation slice
- Treating ODM XML as the only canonical storage format in the first pass if a safer relational canonical model with lossless import/export is preferable

### Key Entities *(include if feature involves data)*

- **Operation Definition**: The stable identity of an activity such as Sample Accession or Visit Data Capture.
- **Operation Version**: A governed draft or published revision of an operation, with SOP references and activation lifecycle.
- **Form Package**: The logical identity of an electronic form or questionnaire family reusable across operations.
- **Form Package Version**: A draft or published version containing questions/fields, sections, edit checks, vocabulary bindings, artifacts, and export/import metadata.
- **Form Section**: A page or logical section within a form package version used for operator-facing grouping and task-level rendering.
- **Item Group**: A logical or repeating group of items/questions within a form package version, similar to CRF group/repeat structures.
- **Form Item**: A version-owned question/field with stable identifier, datatype, label, validation, and vocabulary or logic metadata.
- **Form Artifact**: A stored representation such as ODM XML, XLSX, or import source bundle associated with a form version.
- **Workflow Template**: The design-time task graph attached to an operation version and intended for compilation/execution through Viewflow-compatible runtime patterns.
- **Workflow Node Template**: A task/step definition with assignee rules, permissions, required approvals, task metadata, and form/field bindings.
- **Workflow Edge / Rule**: A transition or conditional branch that decides next steps from prior outcomes or captured data.
- **Operation Run**: A runtime execution of a published operation/workflow version against a subject, specimen, visit, or batch context, analogous to a governed process instance.
- **Task Run**: A runtime record of an individual node execution, including assignee, status, timestamps, approvals, and captured data references, analogous to a governed task instance.
- **Submission / Capture Record**: A record of data entered for a task or form segment, with version references and audit context.
- **Signature / Approval Record**: A governed sign-off record linked to a task run or operation run.
- **Material Usage Record**: A link between a runtime task and specimens, aliquots, batches, or derived artifacts consumed or produced.

## Success Criteria *(mandatory)*

- **SC-001**: The architecture clearly distinguishes design-time operation/form/workflow definitions from runtime execution records.
- **SC-002**: Sample accession can be described end-to-end as a versioned operation with task-specific form capture and QC-driven branching.
- **SC-003**: The form engine is specified as reusable by both LIMS and EDCS rather than being hard-coded to one module.
- **SC-004**: The specification provides enough structure to generate a reviewable issue backlog for domain modeling, form packaging, workflow builder, and runtime execution.
- **SC-005**: The design clearly explains that the already-merged metadata vocabulary/form work is useful but transitional, and must be redefined toward the governed ODM/OpenClinica-style package model instead of being treated as the final target.

## Delivery Mapping *(mandatory)*

- **Primary issue title**: Define shared operation-driven LIMS/EDCS foundation
- **Planned branch label**: `feat/operation-driven-lims-edcs-foundation`
- **Expected PR scope**: specification-first architecture rewrite followed by domain-specific implementation slices
- **Blocking dependencies**: existing metadata/vocabulary work is treated as reusable foundation; no new implementation should start until the architecture spec is reviewed
