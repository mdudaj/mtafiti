# Implementation Plan: LIMS operation foundation with shared form-engine standard

**Feature ID**: `002-operation-driven-lims-edcs-foundation` | **Branch**: `feat/operation-driven-lims-edcs-foundation` | **Date**: 2026-03-19 | **Spec**: `specs/002-operation-driven-lims-edcs-foundation/spec.md`
**Input**: Feature specification from `/specs/002-operation-driven-lims-edcs-foundation/spec.md`

## Summary

Redefine the current LIMS direction around a LIMS-specific operation architecture where versioned operations own mandatory SOP context, standards-aware electronic form packages, Viewflow-compatible workflow templates, task-level metadata capture, branching rules, and auditable runtime execution. The already-merged metadata vocabulary work should be retained, while the earlier versioned-form implementation should be treated as an intermediate step and redefined toward an ODM/OpenClinica-style package model. That form-engine standard remains reusable by both LIMS and EDCS, but the governed operation model in this slice is LIMS-specific, with LIMS Sample Accession as the first governed reference operation and prerequisite for downstream specimen-handling work.

## Technical Context

**Language/Version**: Python 3.12, Django platform under `src/`  
**Primary Dependencies**: Django, django-tenants, Viewflow, django-guardian conventions, Celery, existing LIMS metadata APIs  
**Storage**: PostgreSQL via tenant schemas  
**Testing**: `pytest`, `manage.py check`, `.github/scripts/local_fast_feedback.sh --full-gate`, spec validation via `.github/scripts/spec_kit_workflow.py validate`  
**Target Platform**: tenant-aware `lims` services plus shared form-engine standards that future `edcs` services can consume  
**Project Type**: multi-tenant modular monolith with API-first plus admin-style HTML surfaces  
**Performance Goals**: task forms and workflow execution must remain tenant-safe, auditable, and scalable without duplicating form definitions per task  
**Constraints**: preserve tenant isolation, keep Viewflow as the workflow engine, reuse merged metadata/vocabulary work where possible, and phase stricter compliance features instead of blocking the architectural reset on them  
**Scale/Scope**: architecture/spec rewrite and issue slicing, not full implementation in one increment

## Constitution Check

- [x] The new architecture is captured as a spec-kit source of truth instead of ad hoc chat assumptions.
- [x] Tenant/service-routing implications remain explicit for LIMS operations and for future EDCS consumption of the shared form-engine standard.
- [x] Existing knowledge skills and Viewflow conventions are treated as evidence, not ignored.
- [x] The plan distinguishes design-time configuration entities from runtime execution entities.
- [x] The plan preserves useful metadata/vocabulary work while explicitly redefining the earlier versioned-form slice toward the ODM/OpenClinica target model.

## Research & Knowledge Inputs

### Repository Evidence

- `docs/lab-lims.md` shows the current architecture is still centered on metadata schemas, bindings, biospecimens, and receiving rather than first-class operations.
- `docs/edcs.md` is still a placeholder, which makes this the right time to define a clean boundary where EDCS reuses shared form standards without inheriting LIMS-specific operation/runtime assumptions.
- `docs/workflow-ui.md` and `src/core/models.py` show the existing workflow layer is lightweight and generic: definitions, runs, tasks, orchestration workflows, and transitions exist, but not operation-specific design/runtime boundaries.
- The current `src/lims/` metadata models already provide useful primitives: vocabularies, schema versions, fields, bindings, and validation services, but the form-version model should now be considered transitional and subject to redesign toward package/section/group/item semantics.

### Knowledge Graph / Skills

- `viewflow-configurable-metadata-forms`
- `viewflow-configurable-workflow-runtime-patterns`
- `viewflow-assignment-permission-patterns`
- broader Viewflow/django-material skills already curated in the local Context Hub bundle

### Context Hub Lookups

- During implementation, verify ODM/CDISC import-export conventions, Viewflow-supported topology constraints, and audit/signature best practices against local skills or Context Hub sources.

### External research synthesis

- OpenClinica reinforces that governed form systems need both a visual authoring surface and a spreadsheet/template path for advanced logic, while published form versions remain historically stable.
- OpenClinica’s practical form shape is useful for this architecture: form metadata, sections/pages, item groups including repeats, items/questions, choice lists, revision notes, and stable OIDs/identifiers for import/export and historical rendering.
- OpenClinica’s ODM/XML behavior supports the decision to treat XML as a durable interchange artifact, while still preferring a canonical relational model for runtime querying and workflow integration.
- Viewflow confirms that runtime state should live in explicit `Process` / `Task` models, while orchestration remains in `Flow` definitions using a bounded set of nodes and explicit permission/assignment declarations.
- Viewflow’s supported node family gives the workflow builder a concrete compilation target: `Start`, `StartHandle`, `View`, `Function`, `Handle`, `If`, `Switch`, `Split`, `SplitFirst`, `Join`, and `End`.
- Clinical data-management practice adds two planning constraints that the implementation slices must preserve: governed SOP linkage at operation version level, and form-centric capture where metadata, outcomes, storage-log data, and disposition-log data are first recorded as version-bound submissions before projection into domain models.

## Proposed Domain Direction

### 1. Foundation layers

- Keep `lims` and `edcs` aligned on a shared configurable form-engine standard while allowing the governed operation model to remain LIMS-specific.
- Treat the foundation as four cooperating domains:
   - `operation_config` for LIMS
   - `form_engine`
   - `workflow_config` for LIMS operation execution
   - `workflow_runtime` for LIMS operation execution
- Keep runtime execution records separate from design-time definitions.

### 2. Operation-first model

- Introduce `OperationDefinition` and `OperationVersion` as top-level governed entities.
- Link operation versions to mandatory SOP/version metadata and LIMS module context.
- Make published versions immutable and activate only published operation versions.
- Treat Sample Accession as the required first governed operation for specimens entering LIMS custody, with later specimen-handling operations depending on accession evidence.

### 3. Standards-aware form engine

- Reuse the merged metadata foundation, but explicitly redefine the earlier versioned-form implementation into a more explicit `FormPackage` / `FormPackageVersion` model aligned with ODM/OpenClinica package semantics.
- Prefer a canonical relational persistence model with **lossless ODM/XML and XLSX import/export artifacts** in the first phase.
- Keep controlled vocabularies, edit checks, conditional rules, and presentation hints attached to form package versions.
- Model form structure explicitly around package metadata, sections/pages, item groups/repeats, items/questions, and choice lists with stable identifiers.
- Preserve historical submissions against the exact published form version used at runtime.
- Allow task-level rendering of either full forms, named sections, or explicit field subsets.
- Require operational capture categories such as metadata, outcomes, storage-log entries, and disposition-log entries to originate in published package submissions rather than separate ad hoc data-entry models.

### 4. Workflow configuration

- Attach a workflow template to an operation version.
- Define node/task templates, assignee/permission rules, input/output contracts, and branching conditions.
- Keep the model Viewflow-compatible so approved templates compile to a bounded supported node palette rather than inventing a separate engine.
- Keep assignment and authorization declarative in node metadata so they map cleanly to `Assign(...)` / `Permission(...)` style runtime behavior.
- Keep any future visual workflow-designer surface downstream of these contracts rather than treating UI shapes as the source of truth.

### 5. Workflow runtime

- Introduce runtime entities for `OperationRun`, `TaskRun`, `Submission`, `Approval`, and `MaterialUsage`.
- Preserve references back to operation version, workflow template version, and form package version for auditability.
- Treat these runtime entities as the application’s governed analogue of Viewflow `Process` / `Task` state rather than mixing runtime status into design records.
- Support pause/resume/cancel/delegate and QC-driven short-circuiting at runtime.
- Ensure each governed submission remains traceable to sample/subject context, operation version, SOP version, form version, task/run, and actor.

### 6. Compliance and governance

- Audit every configuration and runtime state transition.
- Model approvals/signatures explicitly now, with stricter compliance packs phased later.
- Keep role-based and object-level permissions consistent with LIMS conventions and future EDCS review workflows.
- Keep GCP/GCLP-aligned traceability expectations explicit even before any stricter Part 11-style implementation slice.

## Reviewable Slices

1. **Architecture ratification**
   - confirm the shared-foundation decision
   - confirm operation-first direction
   - confirm canonical relational model + ODM/XLSX import/export stance

2. **Operation and version domain**
   - define operation identity, versioning, SOP linkage, activation, and tenant/module scope

3. **Form engine evolution**
   - map current metadata schema primitives into form packages, versioned artifacts, edit checks, identifiers/OIDs, and export/import contracts
   - explicitly document which parts of the merged versioned-form work are retained, renamed, or replaced to conform to ODM/OpenClinica-style structure

4. **Workflow builder**
   - define node templates, task-level field/section bindings, branching rules, approval semantics, and Viewflow compilation boundaries around the supported node palette

5. **Controlled vocabulary governance**
   - define how reusable controlled vocabularies, coded decisions, units, and sample classifications remain stable across operation and form package versions

6. **Runtime execution**
   - define operation runs, task runs, capture records, approvals, material usage, and in-flight version behavior

7. **LIMS reference operation**
   - define Sample Accession as the first reference operation using:
     - intake metadata
     - QC accept/reject
     - conditional storage logging
     - auditable completion path

8. **EDCS standards alignment**
   - document how study visits/CRFs reuse the same form-engine and vocabulary standards without forcing the LIMS operation/runtime model into EDCS

## Open Design Decisions

- Whether the shared foundation should live under `src/core/`, `src/workflow_*` style apps, or a new shared configuration domain once implementation starts
- How granular task-level form binding should be: section-based, explicit field lists, or both
- How much of ODM XML will be supported in the first import/export contract versus phased later
- Whether edit checks and workflow branch rules should share one expression language or remain two coordinated rule families
- How electronic signatures are modeled initially: simple approval records now with a later stronger compliance layer
- How much OpenClinica-like spreadsheet fidelity is required in the first version of the import/export contract versus later designer enhancements

## Delivery Mapping

- **Issue title**: Define LIMS operation foundation with shared form-engine standard
- **Issue generation command**: `./.venv/bin/python .github/scripts/spec_kit_workflow.py issue-body specs/002-operation-driven-lims-edcs-foundation`
- **PR generation command**: `./.venv/bin/python .github/scripts/spec_kit_workflow.py pr-body specs/002-operation-driven-lims-edcs-foundation`
- **Branch naming**: `feat/operation-driven-lims-edcs-foundation`
- **Execution slices**: spec ratification first, then separate issues for operation domain, form engine, workflow builder, runtime, and reference operation
- **Dependencies**: builds on existing LIMS metadata vocabulary/form foundation without replacing it blindly

## Planned Validation

- `./.venv/bin/python .github/scripts/spec_kit_workflow.py validate specs/002-operation-driven-lims-edcs-foundation`
- review the new bundle against `docs/lab-lims.md`, `docs/edcs.md`, `docs/workflow-ui.md`, and `src/core/models.py`
- refresh generated inventory/graph artifacts after adding the new spec bundle so docs-gate stays deterministic

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| Shared form-engine standard instead of another LIMS-only metadata increment | The user wants one reusable governed form standard for LIMS and EDCS | A LIMS-only rewrite would duplicate the same governed-form problem later in EDCS |
| Canonical relational model plus ODM/XLSX artifacts | The platform needs safe queryable runtime behavior and standards-aligned interchange | Storing raw ODM XML as the only source of truth would make workflow/task/runtime integration brittle in early slices |
