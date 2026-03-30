# Implementation Plan: Workflow builder foundation

**Feature ID**: `005-workflow-builder-foundation` | **Branch**: `docs/workflow-builder-foundation` | **Date**: 2026-03-19 | **Spec**: `specs/005-workflow-builder-foundation/spec.md`
**Input**: GitHub issue `#110`, the merged architecture/runtime bundles, and the clarified separation between the ODM compiler and the orchestration/UI layers.

## Summary

Define a bounded, Viewflow-compatible workflow-builder subsystem for LIMS operations. This slice focuses on workflow templates, node/edge/rule definitions, assignment and approval metadata, and task capture bindings to compiler-owned package outputs — while explicitly keeping form compilation and validation inside the separate ODM/OpenClinica engine. It stays terminology-compatible with the broader architecture by treating metadata, outcomes, storage-log entries, and disposition-log entries as compiler-owned capture subsets rather than workflow-local field families, and it does not require EDCS to adopt the same workflow-builder model.

## Technical Context

**Language/Version**: Python 3.12, Django under `src/`  
**Primary Dependencies**: Django, django-tenants, Viewflow runtime conventions, future ODM engine outputs, existing core role/audit patterns  
**Storage**: PostgreSQL tenant schemas  
**Testing**: `spec_kit_workflow.py validate`, `python -m pytest -q src/tests/test_spec_kit_workflow.py src/tests/test_knowledge_graph_generator.py`  
**Target Platform**: LIMS workflow configuration foundation aligned to the shared form-engine standard  
**Project Type**: spec-first architecture slice  
**Constraints**: keep topology bounded to Viewflow-compatible patterns, keep compiler logic out of the builder, preserve tenant isolation, preserve deterministic published outputs  
**Scale/Scope**: architecture/specification and issue slicing, not full workflow runtime implementation

## Constitution Check

- [x] The slice preserves the operation-driven architecture already ratified in `002` and `003`.
- [x] The slice respects the clarified boundary that the ODM engine is separate from orchestration/UI.
- [x] The plan keeps workflow configuration separate from workflow runtime execution.
- [x] The plan binds task capture to compiler-owned outputs instead of redefining form semantics.
- [x] The plan keeps the builder explicitly LIMS-specific while preserving compatibility with the shared form-engine standard.

## Research & Repository Evidence

### Current repository evidence

- `docs/workflow-ui.md` already establishes Viewflow as the workflow engine and django-material as a presentation layer.
- `specs/002-operation-driven-lims-edcs-foundation/` defines bounded workflow-node expectations and task-level capture needs.
- `specs/003-operation-runtime-domain/` defines runtime consumers that need published workflow-template outputs.
- `specs/004-odm-form-engine-foundation/` defines the separate compiler/validator subsystem whose published outputs the builder must consume.

### Gaps this slice must close

- no first-class versioned workflow-template model exists yet
- no explicit node/edge/rule/assignment/approval configuration model exists yet
- no formal binding contract exists from tasks to compiler-owned package outputs
- current generic workflow definitions are too thin and too payload-driven for governed execution

## Proposed Design Direction

### 1. Workflow-template identity and versioning

- define `WorkflowTemplate` and `WorkflowTemplateVersion`
- attach templates to operation versions
- keep published workflow-template versions immutable

### 2. Bounded topology model

- define node and edge templates around supported Viewflow-compatible node families
- reject unsupported graph patterns before publication
- keep branch, split, and join semantics explicit and validated

### 3. Node metadata and governance

- define assignment rules, permission requirements, approval requirements, and operator guidance as node metadata
- keep these declarative so runtime enforcement can stay consistent

### 4. Compiler-owned capture bindings

- bind nodes to published package/version/section/group/item outputs from the ODM engine
- support full-package, section, group, or item-subset capture scopes
- keep the builder from inventing or compiling field semantics
- ensure node bindings can cleanly isolate standardized operational capture subsets such as metadata, outcomes, storage logs, and disposition logs while leaving those semantics in the compiler-owned package model

### 5. Runtime-facing outputs

- compile published workflow-template versions into runtime-ready topology, binding, and governance metadata
- ensure runtime can consume these outputs without revalidating authoring-time topology semantics

## Reviewable Slices

1. **Template identity/versioning**
   - define template/version lifecycle and operation attachment

2. **Topology model**
   - define supported node/edge families and publication-time validation

3. **Node governance metadata**
   - define assignment, permission, and approval configuration

4. **Task capture bindings**
   - define how nodes consume compiler-owned form outputs

5. **Runtime output contract**
   - define what the builder emits for workflow runtime consumption

## Open Design Decisions

- whether builder publication emits normalized relational records, JSON topology artifacts, or both
- how expressive branch rules should be in the first implementation slice
- how many assignment strategies to support initially (fixed role, resolver, queue, escalation)
- how to handle template revalidation when referenced form-engine outputs are superseded
- whether some node metadata should be reusable across templates or remain version-local first

## Delivery Mapping

- **Issue title**: Design LIMS configurable workflow builder
- **Issue reference**: `#110`
- **Parent issue**: `#107`
- **Issue generation command**: `./.venv/bin/python .github/scripts/spec_kit_workflow.py issue-body specs/005-workflow-builder-foundation`
- **PR generation command**: `./.venv/bin/python .github/scripts/spec_kit_workflow.py pr-body specs/005-workflow-builder-foundation --issue-number 110`
- **Branch naming**: `docs/workflow-builder-foundation`

## Planned Validation

- `./.venv/bin/python .github/scripts/spec_kit_workflow.py validate specs/005-workflow-builder-foundation`
- `./.venv/bin/python .github/scripts/generate_knowledge_graph.py`
- `./.venv/bin/python -m pytest -q src/tests/test_spec_kit_workflow.py src/tests/test_knowledge_graph_generator.py`
