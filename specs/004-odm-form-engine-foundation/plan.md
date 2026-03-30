# Implementation Plan: ODM form engine foundation

**Feature ID**: `004-odm-form-engine-foundation` | **Branch**: `docs/odm-form-engine-foundation` | **Date**: 2026-03-19 | **Spec**: `specs/004-odm-form-engine-foundation/spec.md`
**Input**: GitHub issue `#109`, the merged architecture/runtime bundles, and the clarification that Django/Viewflow/django-material are orchestration/UI consumers rather than the core form compiler.

## Summary

Define a standalone ODM/OpenClinica-style form engine subsystem that parses, normalizes, validates, compiles, and exports governed form packages. This slice makes the compiler/validator the authority for form meaning, while Django, Viewflow, and django-material remain downstream orchestration/runtime and presentation layers that consume compiled outputs. It also makes the form-centric capture rule explicit: metadata, outcomes, storage-log entries, and disposition-log entries should originate in governed package submissions rather than fragmented ad hoc entry structures.

## Technical Context

**Language/Version**: Python 3.12, Django under `src/`  
**Primary Dependencies**: Django, django-tenants, existing metadata vocabulary models, future parser/compiler services, Context Hub / local knowledge for OpenClinica patterns  
**Storage**: PostgreSQL tenant schemas plus persisted source/export artifacts  
**Testing**: `spec_kit_workflow.py validate`, `python -m pytest -q src/tests/test_spec_kit_workflow.py src/tests/test_knowledge_graph_generator.py`  
**Target Platform**: shared form-engine foundation for `lims` and `edcs`  
**Project Type**: spec-first architecture slice  
**Constraints**: keep compiler logic separate from orchestration and UI, preserve tenant isolation, support deterministic compiled outputs, preserve OpenClinica-style governed versioning  
**Scale/Scope**: architecture/specification and issue slicing, not full compiler implementation

## Constitution Check

- [x] The slice preserves the operation-driven architecture ratified in `002` and `003`.
- [x] The slice explicitly separates compiler responsibilities from orchestration and UI responsibilities.
- [x] The plan uses existing metadata models as migration evidence rather than falsely declaring them the final engine.
- [x] The plan keeps published compiled versions immutable and runtime-safe.
- [x] The plan keeps the engine reusable across LIMS and EDCS.

## Research & Repository Evidence

### Current repository evidence

- `src/lims/models.py` already shows tenant-scoped vocabularies and draft/published metadata schema versions.
- `specs/002-operation-driven-lims-edcs-foundation/` already ratifies OpenClinica-style package semantics and Viewflow as the workflow runtime target.
- `specs/003-operation-runtime-domain/` already defines runtime consumers that need immutable published package-version references.
- `docs/workflow-ui.md` confirms Viewflow and django-material are runtime/UI concerns, not compiler concerns.

### Gaps this slice must close

- no explicit parser/normalizer/validator/compiler subsystem exists yet
- no canonical package/section/group/item model exists yet
- no separation exists between authoring artifacts and compiled outputs
- no explicit compiler-owned render/runtime projection contract exists yet
- current metadata models are still too close to direct UI/runtime consumption

## Proposed Design Direction

### 1. Source artifacts and authoring adapters

- accept XLSX and ODM/XML as first-class source artifact types
- preserve provenance, checksums/fingerprints, source version notes, and import diagnostics
- allow future visual authoring to emit the same draft inputs without changing the compiler core

### 2. Canonical compiler model

- define `FormPackage` and `FormPackageVersion`
- define package metadata, sections/pages, item groups/repeats, items/questions, choice lists, and stable identifiers
- normalize all imported/authored source formats into this model before publication

### 3. Compiler pipeline

- parse artifacts into typed source objects
- normalize into canonical model
- run semantic validation
- compile published versions into runtime/render projections
- emit export artifacts and diagnostics

### 4. Downstream layer contracts

- runtime/workflow layers bind to published package/version references and compiled field/section identifiers
- UI layers consume compiled render contracts and validation hints
- neither layer parses source artifacts or owns semantic validation
- one package family may still be rendered in task-specific subsets so workflows can capture only the relevant sections without creating parallel form definitions

### 5. Migration from current metadata slice

- keep vocabularies as reusable controlled lists
- map current schema/version/field records into transitional authoring assets or migration sources
- retire target-key-driven bindings in favor of package/version references owned by the engine

## Reviewable Slices

1. **Engine boundary definition**
   - define what belongs in compiler core vs orchestration/UI

2. **Canonical package model**
   - define package/version/section/group/item/choice structures

3. **Compiler pipeline**
   - define parse, normalize, validate, compile, export stages

4. **Downstream contracts**
   - define compiled outputs for runtime binding and UI rendering

5. **Migration plan**
   - define reuse/rename/replace rules for current metadata models

## Open Design Decisions

- whether compiled projections are stored as normalized relational entities, generated JSON artifacts, or both
- how much OpenClinica spreadsheet fidelity is required in the first parser adapter
- whether some edit-check authoring stays in XLSX-first form before later visual builder support
- how compiler diagnostics should be persisted and surfaced across draft authoring workflows
- how far first-pass ODM/XML export will go before broader import/export coverage

## Delivery Mapping

- **Issue title**: Design ODM form engine foundation
- **Issue reference**: `#109`
- **Parent issue**: `#107`
- **Issue generation command**: `./.venv/bin/python .github/scripts/spec_kit_workflow.py issue-body specs/004-odm-form-engine-foundation`
- **PR generation command**: `./.venv/bin/python .github/scripts/spec_kit_workflow.py pr-body specs/004-odm-form-engine-foundation --issue-number 109`
- **Branch naming**: `docs/odm-form-engine-foundation`

## Planned Validation

- `./.venv/bin/python .github/scripts/spec_kit_workflow.py validate specs/004-odm-form-engine-foundation`
- `./.venv/bin/python .github/scripts/generate_knowledge_graph.py`
- `./.venv/bin/python -m pytest -q src/tests/test_spec_kit_workflow.py src/tests/test_knowledge_graph_generator.py`
