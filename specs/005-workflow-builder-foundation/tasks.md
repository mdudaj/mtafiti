---

description: "Task list for the workflow builder foundation"
---

# Tasks: Workflow builder foundation

**Input**: Design documents from `/specs/005-workflow-builder-foundation/`
**Prerequisites**: `spec.md` and `plan.md`

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel
- **[Story]**: Maps to a user story such as `US1`
- This task file is specification-first; it defines design and issue-slicing work, not full implementation.

## Phase 1: Builder-boundary ratification

- [ ] T001 Confirm the workflow builder is separate from both the ODM compiler and the workflow runtime.
- [ ] T002 Confirm bounded Viewflow-compatible topology as the design target.
- [ ] T003 Confirm task capture bindings consume compiler-owned package outputs.
- [ ] T004 Confirm assignment, permission, and approval metadata live declaratively in node templates.
- [ ] T005 Generate the issue body with `./.venv/bin/python .github/scripts/spec_kit_workflow.py issue-body specs/005-workflow-builder-foundation`.

---

## Phase 2: Builder detail

- [ ] T010 [US1] Define workflow-template and workflow-template-version lifecycle.
- [ ] T011 [US1] Define supported node and edge template families plus topology validation.
- [ ] T012 [US2] Define task-capture bindings to package/version/section/group/item outputs.
- [ ] T013 [US3] Define assignment, permission, and approval metadata.
- [ ] T014 [US4] Define branch-rule semantics based on outcomes and compiler-owned item identifiers.
- [ ] T015 [US1] Define publication/compilation outputs for runtime consumption.
- [ ] T016 [US5] Define cross-module reuse constraints for both LIMS and EDCS.

---

## Phase 3: Migration and implementation readiness

- [ ] T020 Review current generic workflow definitions and APIs to identify reuse, adaptation, or retirement boundaries.
- [ ] T021 Review runtime-domain and ODM-engine slices to define interface contracts.
- [ ] T022 Decide first implementation issue boundaries for template models, validation/compiler services, and runtime adapters.
- [ ] T023 Generate the eventual PR body with `./.venv/bin/python .github/scripts/spec_kit_workflow.py pr-body specs/005-workflow-builder-foundation --issue-number 110`.

## Notes

- The workflow builder is an orchestration design layer.
- It must never become a shadow form compiler.
- Published workflow templates should bind to published compiler outputs and feed runtime consumers.
