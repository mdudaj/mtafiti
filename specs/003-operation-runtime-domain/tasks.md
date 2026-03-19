---

description: "Task list for the operation runtime domain"
---

# Tasks: Operation runtime domain

**Input**: Design documents from `/specs/003-operation-runtime-domain/`
**Prerequisites**: `spec.md` and `plan.md`

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel
- **[Story]**: Maps to a user story such as `US1`
- This task file is specification-first; it defines design and issue-slicing work, not full implementation.

## Phase 1: Runtime-domain ratification

- [ ] T001 Confirm `OperationDefinition` and `OperationVersion` as first-class governed configuration entities.
- [ ] T002 Confirm immutable version freeze for started runs.
- [ ] T003 Confirm explicit runtime entities for runs, tasks, submissions, approvals, and material usage.
- [ ] T004 Confirm current `core` workflow models are transitional/reusable evidence rather than the final shared runtime model.
- [ ] T005 Generate the issue body with `./.venv/bin/python .github/scripts/spec_kit_workflow.py issue-body specs/003-operation-runtime-domain`.

---

## Phase 2: Domain detail

- [ ] T010 [US1] Define operation definition/version lifecycle, SOP linkage, activation, supersession, and tenant/module scope.
- [ ] T011 [US2] Define `OperationRun`, `TaskRun`, and runtime version-binding behavior.
- [ ] T012 [US2] Define `SubmissionRecord` lifecycle and task/form-segment capture semantics.
- [ ] T013 [US3] Define `ApprovalRecord` semantics, signer context, approval meaning, and audit linkage.
- [ ] T014 [US4] Define `MaterialUsageRecord` semantics and its linkage to existing LIMS artifact aggregates.
- [ ] T015 [US2] Define cancellation, rejection, short-circuit completion, pause/resume, and controlled reopen behavior.
- [ ] T016 [US5] Define EDCS-compatible subject/runtime reference rules without LIMS-only assumptions.

---

## Phase 3: Migration and implementation readiness

- [ ] T020 Review `src/core/models.py` and `src/core/views.py` to identify which workflow primitives can be adapted, wrapped, or retired.
- [ ] T021 Review `src/lims/models.py` accessioning/biospecimen artifacts to identify runtime reference boundaries.
- [ ] T022 Decide first implementation issue boundaries for operation config, runtime entities, approvals/audit, and material usage.
- [ ] T023 Generate the eventual PR body with `./.venv/bin/python .github/scripts/spec_kit_workflow.py pr-body specs/003-operation-runtime-domain --issue-number 108`.

## Notes

- This slice narrows the broader foundation work into a runtime/configuration domain that can be implemented incrementally.
- Existing LIMS artifact domains should be referenced, not duplicated, by the runtime model.
- Existing `core` workflow primitives are useful prior art but should not constrain the governed shared runtime unnecessarily.
