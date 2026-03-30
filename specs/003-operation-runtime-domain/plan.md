# Implementation Plan: Operation runtime domain

**Feature ID**: `003-operation-runtime-domain` | **Branch**: `docs/operation-runtime-domain` | **Date**: 2026-03-19 | **Spec**: `specs/003-operation-runtime-domain/spec.md`
**Input**: GitHub issue `#108` and the parent architecture bundle in `specs/002-operation-driven-lims-edcs-foundation/`

## Summary

Define the LIMS operation runtime/configuration slice that turns the merged foundation architecture into a concrete runtime model: operation definitions and versions, activation lifecycle, operation runs, task runs, task submissions, approvals/signatures, audit linkage, material usage, traceability to SOP/form/sample context, and in-flight version behavior. This slice should explain how to evolve the current generic `core` workflow scaffold into a governed runtime for LIMS while leaving EDCS free to consume the shared form-engine standard through its own execution model.

## Technical Context

**Language/Version**: Python 3.12, Django under `src/`  
**Primary Dependencies**: Django, django-tenants, Viewflow runtime conventions, existing core audit/event publishing, LIMS biospecimen/accessioning models  
**Storage**: PostgreSQL tenant schemas  
**Testing**: `spec_kit_workflow.py validate`, `python -m pytest -q src/tests/test_spec_kit_workflow.py src/tests/test_knowledge_graph_generator.py`  
**Target Platform**: LIMS operation-driven runtime with shared form-engine standards alignment for future `edcs`  
**Project Type**: spec-first architecture slice  
**Constraints**: preserve tenant isolation, preserve explicit Viewflow-style runtime state, keep the runtime boundary explicitly LIMS-specific, and reuse existing artifact models rather than duplicating them  
**Scale/Scope**: specification and issue-slicing only, not full runtime implementation

## Constitution Check

- [x] The slice is grounded in the merged architecture bundle rather than reopening first-principles scope.
- [x] The slice uses current repository evidence from `core` workflow primitives and `lims` artifact models.
- [x] The plan keeps runtime execution distinct from authored operation/form/workflow configuration.
- [x] The plan preserves tenant-aware and audit-aware behavior as first-class requirements.
- [x] The plan keeps the runtime explicitly LIMS-specific while preserving a clean boundary to the shared form-engine standard.

## Research & Repository Evidence

### Current reusable repository primitives

- `src/core/models.py` provides `WorkflowDefinition`, `WorkflowRun`, and `WorkflowTask`, proving the repository already prefers explicit runtime records over implicit state.
- `src/core/views.py` publishes both workflow events and audit events for run creation and transitions, giving the runtime slice an existing event/audit pattern to reuse.
- `docs/workflow-ui.md` anchors the system on Viewflow and server-rendered operator UI, reinforcing the need for explicit process/task records.
- `src/lims/models.py` provides the referenced artifact domains needed for runtime linkage: biospecimens, aliquots, pools, manifests, receiving events, and discrepancies.

### Gaps this slice must close

- generic workflow definitions are unversioned and too lightweight for governed operations
- run/task records do not freeze authored version context
- task capture, approvals, and material usage are not explicit runtime entities
- in-flight version behavior is not yet defined
- subject/artifact references are not yet explicit enough for a durable LIMS runtime boundary

## Proposed Design Direction

### 1. Operation configuration identity

- Introduce `OperationDefinition` as the stable activity identity.
- Introduce `OperationVersion` as the governed authored revision.
- Record LIMS module scope, SOP linkage, status, and activation metadata.

### 2. Runtime version freeze

- When a run starts, create immutable version bindings to:
  - the published operation version
  - the workflow template version used to compile execution
  - the relevant form package version(s)
- Do not mutate those bindings when newer versions are published.

### 3. Explicit runtime entities

- `OperationRun`
- `TaskRun`
- `SubmissionRecord`
- `ApprovalRecord`
- `MaterialUsageRecord`
- optional `RuntimeVersionBinding` if version freeze is modeled independently rather than directly on `OperationRun`

### 4. Audit and event linkage

- Reuse the current event publication and audit publication pattern.
- Make state changes, approvals, overrides, and significant capture steps auditable with stable runtime identifiers and correlation IDs.
- Ensure runtime records can reconstruct who captured what, for which sample/subject, under which operation/SOP/form version context.

### 5. LIMS artifact linkage without duplication

- Reference existing LIMS models for specimens, aliquots, pools, manifests, receiving events, and discrepancies.
- Keep the LIMS runtime relational and explicit by storing typed references or bounded reference families rather than collapsing artifact linkage into opaque payloads.

### 6. In-flight version behavior

- Active/in-progress runs remain on their original version set.
- Draft or queued-not-started runs may follow controlled migration rules, but only if explicitly allowed by the newer version.
- Historical approvals and submissions remain bound to their original authored context.

### 7. Boundary to EDCS

- Keep the runtime anchored to LIMS specimen and laboratory-execution contexts.
- Leave EDCS execution-model concerns out of this slice while preserving compatibility at the shared form-engine boundary.

## Reviewable Slices

1. **Operation definition/version domain**
   - define stable identity, authored versions, SOP linkage, tenant/module scope, activation lifecycle

2. **Runtime records**
   - define operation runs, task runs, runtime version freeze, and queue/status semantics

3. **Capture and approval records**
   - define submission lifecycle, approval/signature records, and audit linkage

4. **Material usage linkage**
   - define how runtime tasks reference consumed and produced artifacts without duplicating LIMS models

5. **In-flight version rules**
   - define what stays fixed, what can migrate, and what must be rejected when versions change

6. **Implementation mapping**
   - map current `WorkflowDefinition` / `WorkflowRun` / `WorkflowTask` into reusable versus transitional pieces

## Open Design Decisions

- Whether runtime version freeze is stored directly on `OperationRun` or normalized into a separate binding table
- Whether `SubmissionRecord` should support multiple draft saves before final submit in the first implementation slice
- Whether approvals are always task-scoped first, or can be operation-scoped without a task run
- How typed artifact references should be represented while staying relational and queryable
- Which currently generic `core` workflow APIs can be adapted versus deprecated when the LIMS runtime lands

## Delivery Mapping

- **Issue title**: Design LIMS operation runtime domain
- **Issue reference**: `#108`
- **Parent issue**: `#107`
- **Issue generation command**: `./.venv/bin/python .github/scripts/spec_kit_workflow.py issue-body specs/003-operation-runtime-domain`
- **PR generation command**: `./.venv/bin/python .github/scripts/spec_kit_workflow.py pr-body specs/003-operation-runtime-domain --issue-number 108`
- **Branch naming**: `docs/operation-runtime-domain`

## Planned Validation

- `./.venv/bin/python .github/scripts/spec_kit_workflow.py validate specs/003-operation-runtime-domain`
- `./.venv/bin/python .github/scripts/generate_knowledge_graph.py`
- `./.venv/bin/python -m pytest -q src/tests/test_spec_kit_workflow.py src/tests/test_knowledge_graph_generator.py`

