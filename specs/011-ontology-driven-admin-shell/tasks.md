---

description: "Task list for the ontology-driven admin application shell"
---

# Tasks: Ontology-driven admin application shell

**Input**: Design documents from `/specs/011-ontology-driven-admin-shell/`
**Prerequisites**: `spec.md` and `plan.md`

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel
- **[Story]**: Maps to a user story such as `US1`
- This task file is specification-first; it defines design and issue-slicing work, not full implementation.

## Phase 1: Shell-boundary ratification

- [ ] T001 Ratify django-material as the baseline shell inheritance strategy and document `material/layout/base.html` as the default parent.
- [ ] T002 Ratify the reuse, extend, override decision tree and isolate the approved override boundary for shell-level structure changes only.
- [ ] T003 Ratify one canonical server-side shell metadata registry as the first source of truth for navigation and contextual actions.
- [ ] T004 Ratify the canonical workflow action contract: `workflow_key`, server-side resolution, and `/workflow/start/<workflow_key>/` route binding.
- [ ] T005 Ratify deny-by-default filtering for permission, tenant scope, workflow resolution, and page-state constraints before any shell descriptor is rendered.

---

## Phase 2: Shell design detail

- [ ] T010 [US1] Define the base shell inheritance contract, content blocks, slot ownership, and isolated override boundaries.
- [ ] T011 [US2] Define the `NavigationItem` descriptor shape, registry ownership rules, and sidebar rendering contract.
- [ ] T012 [US2] Define supported page-type wrappers plus the shared slots for heading, actions, main content, and workflow guidance.
- [ ] T013 [US3] Define the descriptor-resolution pipeline and deny-by-default filtering semantics for navigation and contextual actions.
- [ ] T014 [US4] Define the reusable FAB or speed-dial component contract, responsive fallback behavior, and canonical workflow-start rules.
- [ ] T015 [US1] Define CSS and JS extension hooks that preserve Materialize compatibility, tooltip initialization, and mobile collision handling.

---

## Phase 3: Migration and implementation readiness

- [ ] T020 Map three proving surfaces for the first implementation: one dashboard, one CRUD page, and one workflow entry or task page.
- [ ] T021 Split the first implementation issues into shell layout, descriptor registry plus navigation resolution, and FAB plus shared action-slot behavior.
- [ ] T022 Review current workflow UI docs and `/api/v1/ui/operations/*` surfaces to define how existing backend payloads feed the proving surfaces.
- [ ] T023 Define how reusable components, template tags, and skills should be registered or documented for the shell layer without duplicating shell metadata ownership.
- [ ] T024 Generate the issue body with `./.venv/bin/python .github/scripts/spec_kit_workflow.py issue-body specs/011-ontology-driven-admin-shell` and verify that it reflects the resolved contracts.
- [ ] T025 Generate the eventual PR body with `./.venv/bin/python .github/scripts/spec_kit_workflow.py pr-body specs/011-ontology-driven-admin-shell`.

## Notes

- The shell must remain django-material-first and server-rendered.
- The shell must not hardcode navigation or contextual actions outside the chosen ontology-driven source of truth.
- Override is a controlled exception, not the default implementation style.