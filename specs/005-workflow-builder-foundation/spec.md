# Feature Specification: Workflow builder foundation

**Feature ID**: `005-workflow-builder-foundation`  
**Execution Branch**: `docs/workflow-builder-foundation`  
**Created**: 2026-03-19  
**Status**: Draft  
**Input**: GitHub issue `#110` plus clarified architecture that the ODM/OpenClinica engine is separate from orchestration/UI layers.

## Repository Context *(mandatory)*

- **Service area**: `lims` workflow configuration foundation consuming the shared form-engine standard
- **Affected code paths**: `src/core/models.py`, `src/core/views.py`, `docs/workflow-ui.md`, future shared workflow-config app(s), future workflow-runtime app(s)
- **Related design docs**: `specs/002-operation-driven-lims-edcs-foundation/spec.md`, `specs/003-operation-runtime-domain/spec.md`, `specs/004-odm-form-engine-foundation/spec.md`, `docs/workflow-ui.md`
- **Prior checkpoints**: `022-architecture-spec-and-skills.md`, `019-reference-ux-and-routing.md`, `017-accession-wizard-and-metadata.md`
- **Knowledge graph / skills evidence**: `viewflow-governed-workflow-definition-patterns`, `viewflow-configurable-workflow-runtime-patterns`, `viewflow-assignment-permission-patterns`
- **External API lookup needs**: verify Viewflow-supported topology and task/permission patterns during implementation
- **Related issues / PRs**: parent issue `#107`, scoped issue `#110`, conceptual dependency `#109`, merged architecture/runtime PRs `#112` and `#113`, open ODM engine PR `#114`

## Problem Statement

The repository already knows it wants Viewflow-compatible workflow semantics and explicit runtime `Process`/`Task`-style records. It also now explicitly knows that the ODM/OpenClinica engine is a separate compiler/validation subsystem.

What is still missing is the workflow-builder layer that translates authored operational steps into a governed, bounded, executable workflow-template model while staying downstream of the compiler.

The workflow builder must therefore solve a narrower problem than a generic low-code graph editor:

- define task/node templates and edge/rule templates
- constrain topology to Viewflow-supported semantics
- bind task capture to compiler-owned package/section/group/item references
- define assignee, permission, approval, and branching behavior
- compile configuration into workflow-runtime-ready templates

It must **not** become a shadow form compiler or an unconstrained graph engine.

## Goals

- Define a bounded workflow-template model for LIMS operations using Viewflow-compatible semantics.
- Define task/node, edge, branch-rule, assignment, permission, and approval configuration.
- Define how workflow nodes bind to compiler-owned form package outputs rather than form authoring artifacts.
- Define compilation constraints from authored workflow templates into runtime-ready topology.
- Define migration boundaries from current generic `WorkflowDefinition` scaffolding.

## Non-Goals

- A full drag-and-drop browser workflow studio in the first slice
- Replacing Viewflow with another orchestration engine
- Parsing or compiling ODM/XML/XLSX inside the workflow layer
- Owning task form semantics that belong to the ODM engine
- Full runtime implementation of task execution in this specification slice

## Architectural Position

This slice assumes the following layering:

1. **ODM engine**
   - owns form parsing, normalization, validation, compilation, and published package outputs
2. **Workflow builder**
   - owns node/edge/rule/assignment/approval template design
   - binds to compiler-owned package/version/section/group/item references
3. **Workflow runtime**
   - owns task progression, task creation, transitions, approvals, and execution state
4. **UI layer**
   - renders workflow-builder/admin surfaces and runtime work queues

The workflow builder is an orchestration design subsystem, not a form compiler.

## Viewflow-inspired Builder Direction

The builder must target a bounded node family aligned with Viewflow-style execution:

- `Start`
- `StartHandle`
- `View`
- `Function`
- `Handle`
- `If`
- `Switch`
- `Split`
- `SplitFirst` where supported/needed
- `Join`
- `End`

The builder should compile authored templates only into supported topology and reject unsupported arbitrary graph semantics.

## Workflow Template Scope

### Template-owned concepts

- `WorkflowTemplate`
- `WorkflowTemplateVersion`
- `WorkflowNodeTemplate`
- `WorkflowEdgeTemplate`
- `BranchRule`
- `AssignmentRule`
- `PermissionRequirement`
- `ApprovalRequirement`
- `TaskCaptureBinding`

### Node responsibilities

A node template may define:

- node type and execution role
- task title/summary/operator guidance
- assignee rule(s)
- permission rule(s)
- approval requirement(s)
- capture binding to compiled form package/version/section/group/item references
- input/output data contracts
- transition outcomes and branch triggers

### What nodes must not own

- raw form compilation logic
- ODM/XLSX parsing logic
- canonical form-structure derivation
- UI-specific rendering implementation details beyond consuming compiled projections

## Binding Contract with the ODM Engine

The workflow builder should bind only to compiler-owned published outputs such as:

- `FormPackageVersion`
- `CompiledFormProjection`
- section identifiers
- item-group identifiers
- item identifiers
- compiler-owned validation/edit-check references where relevant

This means:

- task configuration can select full package, section subsets, group subsets, or explicit item subsets
- workflow rules can reference compiler-owned stable identifiers and output values
- the builder cannot invent fields or mutate published form semantics
- task capture bindings should be able to address the standardized operational categories defined elsewhere in the architecture, including metadata, outcomes, storage-log entries, and disposition-log entries, by selecting the relevant compiler-owned subsets rather than inventing workflow-local fields

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Define bounded task graphs for an operation version (Priority: P1)

As a workflow designer, I want to define a task graph for an operation version using supported node types so templates remain executable and reviewable.

**Independent Test**: Define a Sample Accession workflow with `Start -> Intake -> QC -> (Accept -> Storage | Reject -> End)` using only supported node and edge types, then validate the template compiles to an allowed runtime topology.

**Acceptance Scenarios**:

1. **Given** an operation version exists, **When** a designer creates a workflow template version, **Then** only supported node types can be selected.
2. **Given** a designer authors an unsupported arbitrary loop or graph pattern, **When** validation runs, **Then** the builder rejects it before runtime compilation.
3. **Given** a valid template is published, **When** runtime consumers resolve it, **Then** it exposes a bounded executable topology.

---

### User Story 2 - Bind task capture to compiled form outputs (Priority: P1)

As a workflow designer, I want each task to reference compiled package sections/groups/items so capture scope is explicit without redefining form structure.

**Independent Test**: Configure an intake task to capture package sections A and B, a QC task to capture only decision items, and a storage task to capture storage-placement items, all by binding to compiler-owned references.

**Acceptance Scenarios**:

1. **Given** a task needs the whole form package, **When** binding is configured, **Then** the task references the published compiled package version.
2. **Given** a task needs only a subset, **When** binding is configured, **Then** the task references compiled section/group/item identifiers rather than redefining fields.
3. **Given** the underlying package is superseded later, **When** historical task templates are reviewed, **Then** their bindings still resolve to the originally published package version.

---

### User Story 3 - Declare assignment, permissions, and approvals in node metadata (Priority: P1)

As a system administrator, I want assignee, permission, and approval rules defined declaratively in the workflow template so runtime enforcement stays consistent.

**Independent Test**: Configure QC review to require a QA approver role and an approval step, then verify the published template exposes explicit assignment and permission metadata for runtime enforcement.

**Acceptance Scenarios**:

1. **Given** a node requires execution by a specific role, **When** assignment rules are authored, **Then** they are stored as node metadata rather than hidden in view code.
2. **Given** a node requires approval, **When** approval requirements are configured, **Then** the template records sign-off semantics explicitly.
3. **Given** a runtime engine consumes the template, **When** it enforces permissions, **Then** it can derive them from published workflow metadata.

---

### User Story 4 - Drive branching from prior outcomes without colliding with compiler concerns (Priority: P2)

As a workflow designer, I want branching rules based on prior task outcomes or captured values so execution paths remain configurable while form semantics stay compiler-owned.

**Independent Test**: Configure QC to branch on a compiler-owned decision item value and verify that the workflow layer consumes the value/reference without redefining validation or item meaning.

**Acceptance Scenarios**:

1. **Given** a branch depends on a prior task decision, **When** the rule is authored, **Then** it references stable task outcome or compiled item identifiers.
2. **Given** a rule depends on form data, **When** it is evaluated, **Then** it uses compiler-owned identifiers and runtime submission values.
3. **Given** the rule requires form semantics, **When** validation occurs, **Then** the builder relies on compiler contracts rather than re-parsing form definitions.

---

### User Story 5 - Keep workflow configuration aligned to the shared form-engine standard (Priority: P2)

As a platform architect, I want the LIMS workflow builder to consume the same form-engine standard that EDCS uses, without assuming EDCS must also adopt the LIMS workflow-builder model.

**Independent Test**: Confirm a LIMS workflow template binds to the same published package standard that a future EDCS implementation could consume through a different execution model.

**Acceptance Scenarios**:

1. **Given** EDCS later uses the same published package standard, **When** forms are bound there, **Then** the shared compiler-owned package semantics remain compatible without requiring the LIMS workflow builder.
2. **Given** LIMS-specific workflow templates evolve, **When** the shared form-engine standard is reviewed, **Then** EDCS-facing form semantics remain reusable even if orchestration models differ.

## Edge Cases

- How are parallel branches and join semantics constrained so only supported patterns publish?
- How are branch rules validated when they reference compiler-owned item identifiers that disappear in a newer package version?
- How are templates versioned when a downstream form package version is superseded but active templates must remain stable?
- How should hidden/skipped tasks be represented for auditability when branch rules short-circuit the path?
- Which rule logic belongs to workflow branching versus compiler-owned validation/edit checks?
- How are approval rules modeled when multiple approvers or fallback assignees exist?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST define a first-class workflow-template model attached to an operation version.
- **FR-002**: The workflow-template model MUST support draft and published versions with immutable published content.
- **FR-003**: The builder MUST constrain authored templates to a bounded node family compatible with Viewflow-supported execution semantics.
- **FR-004**: The builder MUST reject unsupported arbitrary graph semantics before publication.
- **FR-005**: The builder MUST define node templates with assignee, permission, approval, and capture metadata.
- **FR-006**: The builder MUST define edge and branch-rule models for transitions based on prior outcomes or captured values.
- **FR-007**: The builder MUST bind task capture only to compiler-owned published package/version/section/group/item references.
- **FR-008**: The builder MUST NOT own form parsing, form compilation, or canonical form-structure derivation.
- **FR-009**: The builder MUST support full-package, section-based, group-based, and item-subset task capture bindings.
- **FR-010**: The builder MUST support declarative assignment and permission rules suitable for runtime enforcement.
- **FR-011**: The builder MUST support explicit approval requirements as node metadata.
- **FR-012**: Branch rules that depend on form data MUST reference compiler-owned stable identifiers and runtime submission values.
- **FR-013**: Published workflow templates MUST remain bound to the specific published form-engine outputs they were validated against.
- **FR-014**: The builder MUST provide a compilation/validation step that emits runtime-ready workflow-template outputs.
- **FR-015**: The builder MUST remain a LIMS-specific workflow-configuration layer while consuming form-engine outputs that EDCS can also reuse independently.
- **FR-016**: The builder MUST preserve tenant isolation across workflow templates, rules, bindings, and published outputs.
- **FR-017**: The builder MUST support task-level bindings that can isolate standardized operational capture subsets such as metadata, outcomes, storage-log fields, and disposition-log fields without redefining their semantics in workflow configuration.

### Non-Functional Requirements

- **NFR-001**: Workflow-template compilation outputs MUST be deterministic so CI and runtime consumers see stable topology definitions.
- **NFR-002**: Validation errors MUST clearly distinguish topology failures, binding failures, and permission/approval configuration failures.
- **NFR-003**: Separation of concerns MUST be explicit enough that code review can distinguish workflow-builder logic from compiler logic and runtime logic.

### Key Entities *(include if feature involves data)*

- **WorkflowTemplate**: Stable identity of an orchestration design attached to an operation.
- **WorkflowTemplateVersion**: Draft or published version of the authored workflow template.
- **WorkflowNodeTemplate**: One configured task/node within a template.
- **WorkflowEdgeTemplate**: Directed transition between nodes.
- **BranchRule**: Declarative rule deciding path selection from outcomes or captured values.
- **AssignmentRule**: Declarative assignee resolution metadata.
- **PermissionRequirement**: Role/object-permission requirement for task visibility or execution.
- **ApprovalRequirement**: Explicit sign-off requirement attached to a node.
- **TaskCaptureBinding**: Reference from a node to compiler-owned form package/version/section/group/item outputs.

## Proposed Mapping to Current Repository

### Reuse

- reuse `docs/workflow-ui.md` and existing Viewflow alignment as orchestration evidence
- reuse current role-gated transition patterns in `src/core/views.py` as runtime prior art
- reuse the runtime-domain design in `003` as the target consumer of published workflow templates

### Redefine or replace

- current `WorkflowDefinition` should not be treated as the final workflow-template design model
- current generic workflow APIs are scaffolding and may become adapters or be retired when the governed template model lands
- workflow-builder capture metadata should bind to compiler outputs rather than generic payload-driven fields

## Success Criteria *(mandatory)*

- **SC-001**: The spec clearly defines the workflow builder as separate from both the ODM compiler and workflow runtime.
- **SC-002**: The spec defines a bounded, Viewflow-compatible template model rather than an unconstrained graph editor.
- **SC-003**: The spec makes task capture binding depend on compiler-owned package outputs.
- **SC-004**: The spec is implementation-ready enough to drive a dedicated workflow-builder issue or PR slice.
- **SC-005**: The spec keeps LIMS and EDCS on one reusable orchestration design model.

## Delivery Mapping *(mandatory)*

- **Issue title**: Design configurable workflow builder
- **Issue reference**: `#110`
- **Parent issue**: `#107`
- **Issue generation command**: `./.venv/bin/python .github/scripts/spec_kit_workflow.py issue-body specs/005-workflow-builder-foundation`
- **PR generation command**: `./.venv/bin/python .github/scripts/spec_kit_workflow.py pr-body specs/005-workflow-builder-foundation --issue-number 110`
- **Branch naming**: `docs/workflow-builder-foundation`
