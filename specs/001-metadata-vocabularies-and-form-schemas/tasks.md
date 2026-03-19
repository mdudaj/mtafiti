---

description: "Task list for metadata vocabularies and configurable form schemas"
---

# Tasks: Metadata vocabularies and configurable form schemas

**Input**: Design documents from `/specs/001-metadata-vocabularies-and-form-schemas/`
**Prerequisites**: `spec.md` and `plan.md`

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel
- **[Story]**: Maps to a user story such as `US1`
- This initial task file captures spec ratification and future execution slices; it does not start implementation by itself.

## Phase 1: Specification ratification

- [ ] T001 Confirm the vocabulary-domain model and tenant scope in `specs/001-metadata-vocabularies-and-form-schemas/spec.md`
- [ ] T002 Confirm that fields belong directly to form versions and that published versions are immutable
- [ ] T003 Confirm the runtime binding lifecycle for draft vs. published form versions
- [ ] T004 Generate the initial GitHub issue body with `python .github/scripts/spec_kit_workflow.py issue-body specs/001-metadata-vocabularies-and-form-schemas`

---

## Phase 2: Implementation planning slices

- [ ] T010 [US1] Design the vocabulary domain model and provisioning approach
- [ ] T011 [US1] Specify searchable vocabulary and vocabulary-item REST endpoints for widget consumption
- [ ] T012 [US2] Specify shared single-select and multi-select widget contracts against those REST endpoints
- [ ] T013 [US3] Design the form definition, form version, and form-version-owned field data model
- [ ] T014 [US3] Specify the two-step authoring flow: form metadata first, field builder second
- [ ] T015 [US4] Specify published-version binding and activation rules for runtime targets

---

## Phase 3: Pre-implementation readiness

- [ ] T020 Review the spec and plan against current `src/lims/models.py`, `src/lims/services.py`, `src/lims/views.py`, and `src/tests/test_lims_metadata_api.py`
- [ ] T021 Decide whether to create one implementation issue or multiple scoped issues from this bundle
- [ ] T022 Generate the eventual PR body with `python .github/scripts/spec_kit_workflow.py pr-body specs/001-metadata-vocabularies-and-form-schemas`

## Notes

- This feature bundle is intentionally specification-first.
- No implementation should begin until the spec and plan are reviewed and the issue/task slicing is accepted.
