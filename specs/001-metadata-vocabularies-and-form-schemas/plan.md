# Implementation Plan: Metadata vocabularies and configurable form schemas

**Feature ID**: `001-metadata-vocabularies-and-form-schemas` | **Branch**: `feat/metadata-vocabularies-and-form-schemas` | **Date**: 2026-03-19 | **Spec**: `specs/001-metadata-vocabularies-and-form-schemas/spec.md`
**Input**: Feature specification from `/specs/001-metadata-vocabularies-and-form-schemas/spec.md`

## Summary

Revise the metadata configuration domain before further implementation so that controlled vocabularies become tenant-scoped, functionally organized, searchable through dedicated REST APIs, and easy to provision, while configurable forms evolve toward an ODK-style model where fields belong directly to versioned form definitions with explicit draft and published lifecycle states.

## Technical Context

**Language/Version**: Python 3.12, Django platform under `src/`  
**Primary Dependencies**: Django, django-tenants, Celery, existing LIMS metadata APIs and templates  
**Storage**: PostgreSQL via tenant schemas  
**Testing**: `pytest`, `manage.py check`, `.github/scripts/local_fast_feedback.sh --full-gate`  
**Target Platform**: tenant-aware LIMS service under the Mtafiti platform  
**Project Type**: multi-tenant web platform with API-first plus admin-style UI  
**Performance Goals**: searchable option APIs should support large vocabularies without full client downloads  
**Constraints**: preserve tenant isolation, role-based permissions, auditable state transitions, and compatibility with existing metadata validation flows  
**Scale/Scope**: metadata configuration foundation for LIMS now, designed to support broader workflow-driven forms later

## Constitution Check

- [x] Specifications remain the source of truth for this slice.
- [x] Tenant and service routing impacts are identified.
- [x] Knowledge graph / skill / Context Hub inputs are captured where needed.
- [x] Validation expectations and merge-gate commands are identified for later implementation.
- [x] Issue, branch, and PR mapping are consistent with the spec.

## Research & Knowledge Inputs

### Repository Evidence

- Current metadata models and APIs already exist in `src/lims/models.py`, `src/lims/services.py`, and `src/lims/views.py`.
- Current tests in `src/tests/test_lims_metadata_api.py` prove the existing domain supports vocabularies, field definitions, schema versions, bindings, and validation, but not the revised vocabulary-domain model or ODK-style field ownership.
- `docs/lab-lims.md` and the current session plan already position metadata as a shared configurable foundation for downstream workflows.

### Knowledge Graph / Skills

- Existing LIMS and configurable metadata design direction in the session plan
- Local skills: `viewflow-configurable-metadata-forms`, `viewflow-configurable-workflow-runtime-patterns`

### Context Hub Lookups

- During implementation, verify external patterns for searchable select widgets, schema-driven forms, and controlled vocabulary UX with Context Hub or local skills as needed.

## Project Structure

### Documentation (this feature)

```text
specs/001-metadata-vocabularies-and-form-schemas/
├── spec.md
├── plan.md
└── tasks.md   # to be created when implementation is approved
```

### Source Code (repository root)

```text
src/lims/models.py
src/lims/services.py
src/lims/views.py
src/lims/urls.py
src/lims/templates/lims/
src/tests/test_lims_metadata_api.py
docs/lab-lims.md
docs/spec-kit-workflow.md
```

## Proposed Domain Direction

### Controlled vocabularies

- Keep vocabularies tenant-scoped by default.
- Introduce a functional-domain concept so vocabularies can be grouped by purpose, such as roles, outcomes, consent, units, statuses, or workflow-specific enumerations.
- Add dedicated REST endpoints for:
  - vocabulary domain listing,
  - vocabulary listing/filtering by domain,
  - vocabulary item search for widget consumption.
- Design initial provisioning so a tenant can receive a default vocabulary pack without manual API bootstrapping.
- Keep the first pass extensible for unforeseen vocabularies by allowing admins to create new domains and new vocabularies through configuration.

### Configurable forms

- Shift from reusable global field definitions toward form-version-owned fields.
- Keep a top-level form definition entity for metadata such as name, code, purpose, and target applicability.
- Model separate form versions with explicit draft and published states.
- Treat published versions as immutable, with new changes performed in new draft versions.
- Bind only published versions to runtime targets.

### Authoring workflow

- Step 1: create or edit form metadata and establish a draft version.
- Step 2: open a dedicated field builder for that draft version and define fields owned by the version.
- Future UI can borrow ODK-style form-definition patterns, but the first deliverable is the data and API contract.

## Reviewable Slices

1. **Specification ratification**
   - confirm vocabulary-domain model, provisioning strategy, and ODK-style field ownership
   - confirm lifecycle states and binding rules

2. **Data-model revision**
   - replace or evolve the current field-definition/schema model into form definitions, form versions, and form-version-owned fields
   - add vocabulary domain / provisioning support

3. **Vocabulary APIs**
   - dedicated searchable REST endpoints for vocabularies and items
   - display-ready payloads for select/multi-select widgets

4. **Form authoring APIs**
   - create form metadata
   - create/edit draft form versions
   - add/edit form-version fields
   - publish and activate versions

5. **UI workflow**
   - launchpad + dedicated task pages for vocabulary/domain management
   - two-step form creation and field-builder flow

6. **Validation and migration**
   - preserve existing tenant isolation and metadata validation guarantees
   - add migration path from the current metadata schema model to the revised form/version model

## Open Design Decisions

- Whether vocabulary domains should be standalone records or a coded attribute on vocabularies
- Whether initial provisioning is delivered via fixtures, migration-driven bootstrap, service-layer tenant bootstrap, or admin-triggered import
- How much backward compatibility to preserve for the current `MetadataFieldDefinition` / `MetadataSchemaVersion` model versus introducing a cleaner replacement model
- Whether published vocabulary items need soft-deprecation semantics in the first pass or can remain active/inactive only

## Delivery Mapping

- **Issue title**: Define metadata vocabularies and configurable form schema foundation
- **Issue generation command**: `python .github/scripts/spec_kit_workflow.py issue-body specs/001-metadata-vocabularies-and-form-schemas`
- **PR generation command**: `python .github/scripts/spec_kit_workflow.py pr-body specs/001-metadata-vocabularies-and-form-schemas`
- **Branch naming**: `feat/metadata-vocabularies-and-form-schemas`
- **Execution slices**: spec ratification first, then model/API/UI slices in separate issues or tightly scoped PRs
- **Dependencies**: no implementation dependency for this specification slice

## Planned Validation

- `python .github/scripts/spec_kit_workflow.py validate specs/001-metadata-vocabularies-and-form-schemas`
- review the spec and plan against current repository metadata APIs and tests
- when implementation begins: targeted metadata tests plus `.github/scripts/local_fast_feedback.sh --full-gate`

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| Metadata model revision across models, APIs, and UI | The current model does not match the requested vocabulary-domain and form-version ownership design | Incremental UI tweaks would preserve the wrong underlying abstraction |
