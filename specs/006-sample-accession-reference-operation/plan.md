# Implementation Plan: Sample Accession reference operation

**Feature ID**: `006-sample-accession-reference-operation` | **Branch**: `docs/sample-accession-reference-operation` | **Date**: 2026-03-19 | **Spec**: `specs/006-sample-accession-reference-operation/spec.md`
**Input**: GitHub issue `#111`, the merged operation/runtime/compiler/workflow bundles, and the current LIMS receiving behavior documented in `docs/lab-lims.md`.

## Summary

Define Sample Accession as the first concrete reference operation on the LIMS-specific operation foundation. This slice turns the existing receiving flow into a governed operation with explicit operation-version identity, mandatory SOP context, compiler-owned form bindings, bounded workflow topology, auditable runtime records, and a clean mapping from current `/lims/receiving/*` entrypoints into the future operation runtime.

## Technical Context

**Language/Version**: Python 3.12, Django under `src/`  
**Primary Dependencies**: Django, django-tenants, Viewflow runtime conventions, future ODM-engine compiler outputs, current LIMS accessioning/biospecimen models  
**Storage**: PostgreSQL tenant schemas  
**Testing**: `spec_kit_workflow.py validate`, `python -m pytest -q src/tests/test_spec_kit_workflow.py src/tests/test_knowledge_graph_generator.py`  
**Target Platform**: `lims` reference operation on the LIMS-specific operation/workflow/runtime foundation with a shared form-engine standard  
**Project Type**: spec-first architecture/reference-operation slice  
**Constraints**: preserve compiler/runtime/workflow separation, keep the reference operation implementation-ready, reuse current receiving behavior as transitional prior art, preserve tenant-safe auditability  
**Scale/Scope**: architecture and issue-slicing for one concrete operation, not full runtime implementation

## Constitution Check

- [x] The slice preserves the LIMS-specific operation architecture from `002` while remaining aligned to the shared form-engine standard.
- [x] The slice uses the explicit runtime-version-freeze and governed runtime concepts from `003`.
- [x] The slice keeps the ODM engine separate from orchestration and UI per `004`.
- [x] The slice binds tasks to compiler-owned outputs and keeps the workflow builder separate from runtime per `005`.
- [x] The slice treats current receiving routes as transitional adapters, not the final architecture boundary.

## Research & Repository Evidence

### Current repository evidence

- `docs/lab-lims.md` already documents single receipt, batch manifest, and EDC-linked intake surfaces.
- The current receiving UX already models the key business branch:
  - capture intake data
  - perform first QC decision
  - if accepted, record storage
  - if rejected, record discrepancy
- `src/lims/models.py` and related services already provide biospecimen, manifest, receiving event, and discrepancy aggregates that the future operation runtime can reference.
- The newly merged `002` / `003` / `004` / `005` bundles provide the contracts this reference operation must now prove.

### Gaps this slice must close

- no concrete reference operation yet shows how all four architecture layers fit together
- current receiving behavior is practical but not yet framed as a versioned governed operation
- task-level bindings to compiler-owned package outputs are not yet demonstrated by one canonical example
- the current receiving pages and APIs need a clear target-state mapping into future runtime concepts

## Proposed Design Direction

### 1. Stable operation identity

- define `sample-accession` as the first stable operation code
- attach SOP/version context and lifecycle metadata
- use it as the LIMS exemplar and prerequisite entry point for later specimen-handling operations

### 2. One canonical accession workflow

- start from the real current flow:
  - intake capture
  - QC decision
  - accepted path to storage
   - rejected path to discrepancy and disposition closure
- publish this as the bounded workflow-template shape for the operation

### 3. Compiler-owned capture bindings

- define one primary accession form package family
- bind tasks to package sections/items instead of redefining fields in UI or workflow code
- allow manifest and EDC intake to prefill values while preserving one canonical package contract
- require metadata, outcomes, storage-log entries, and disposition-log entries to originate in task-bound governed submissions before projection into biospecimen and receiving-side models

### 4. Runtime evidence model

- map accession execution to `OperationRun`, `TaskRun`, `SubmissionRecord`, `ApprovalRecord`, and `MaterialUsageRecord`
- explicitly link runs to biospecimens, manifest items, receiving events, discrepancies, and future storage artifacts
- preserve traceability from each captured value and branch decision back to specimen/intake context, operation version, SOP version context, form package version, and actor

### 5. Transitional migration path

- keep `/lims/receiving/` as the launchpad
- keep `/lims/receiving/single/`, `/lims/receiving/batch/`, and `/lims/receiving/edc-import/` as operator entrypoints
- reinterpret them as adapters that initiate governed accession runs and submit task-scoped data

## Reviewable Slices

1. **Operation identity and lifecycle**
   - define the stable `sample-accession` operation identity and published version behavior

2. **Workflow and branch contract**
   - define the canonical intake -> QC -> storage/rejection shape

3. **Compiler binding contract**
   - define package sections/items consumed by each task

4. **Runtime evidence contract**
   - define runs, task runs, submissions, audit events, and material links

5. **Current-to-target migration**
   - define how current APIs and UI surfaces become governed runtime adapters

## Open Design Decisions

- whether accession should use one package family with section subsets or multiple tightly related packages in the first implementation
- whether QC requires a formal `ApprovalRecord` in the first runtime increment or only an outcome plus audit entry
- how much of storage placement should be explicit before the storage domain is fully implemented
- how batch manifest items should represent pre-start, started, and completed accession status
- how EDC-prefill provenance should be stored for later audit and troubleshooting

## Delivery Mapping

- **Issue title**: Define Sample Accession as reference operation
- **Issue reference**: `#111`
- **Parent issue**: `#107`
- **Issue generation command**: `./.venv/bin/python .github/scripts/spec_kit_workflow.py issue-body specs/006-sample-accession-reference-operation`
- **PR generation command**: `./.venv/bin/python .github/scripts/spec_kit_workflow.py pr-body specs/006-sample-accession-reference-operation --issue-number 111`
- **Branch naming**: `docs/sample-accession-reference-operation`

## Planned Validation

- `./.venv/bin/python .github/scripts/spec_kit_workflow.py validate specs/006-sample-accession-reference-operation`
- `./.venv/bin/python .github/scripts/generate_knowledge_graph.py`
- `./.venv/bin/python -m pytest -q src/tests/test_spec_kit_workflow.py src/tests/test_knowledge_graph_generator.py`
