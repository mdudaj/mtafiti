---

description: "Task list for ontology-driven operational pages"
---

# Tasks: Ontology-driven operational pages

**Input**: Design documents from `/specs/012-ontology-driven-operation-pages/`  
**Prerequisites**: `spec.md` and `plan.md`

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel
- **[Story]**: Maps to a user story such as `US1`
- This task file is specification-first; it defines design and issue-slicing work, not full implementation.

## Phase 1: Page-pattern ratification

- [ ] T001 Ratify operation pages as a new feature bundle that depends on `011` rather than expanding shell scope directly.
- [ ] T002 Ratify `ActionCard` as the canonical operational entry descriptor with mutually exclusive `route` and `workflow_key` bindings.
- [ ] T003 Ratify the deterministic resolver pipeline for permission, state, and data-availability filtering before render.
- [ ] T004 Ratify the bounded page-density rule, including the hard cap of 8 ungrouped cards.
- [ ] T005 Ratify the rule that FAB can only mirror one allowed card action and cannot introduce new action authority.

---

## Phase 2: Operation-page design detail

- [ ] T010 [US1] Define the `OperationPage` contract, including page identity, page scope, and shell integration rules.
- [ ] T011 [US2] Define the authored and computed fields for the reusable `ActionCard` descriptor.
- [ ] T012 [US1] Define the django-material-compatible card-grid layout, full-card click behavior, and reusable component template contract.
- [ ] T013 [US3] Define deterministic ordering, tie-breaking, and deny-by-default exclusion rules.
- [ ] T014 [US4] Define optional FAB derivation, explicit primary-action behavior, and suppression rules.
- [ ] T015 [US3] Define dynamic card-generation rules for workflow state, user role, and data-availability context.

---

## Phase 3: Implementation readiness

- [ ] T020 Map three proving surfaces: one route-heavy intake page, one mixed route-and-workflow page, and one state-sensitive page.
- [ ] T021 Split the GitHub issues into one parent spec issue plus three implementation issues: descriptor resolution, reusable rendering, and proving surfaces plus FAB derivation.
- [ ] T022 Review current `/api/v1/ui/operations/*` payloads and operational templates to define how allowed-action payloads can feed the descriptor-resolution issue.
- [ ] T023 Define how component registration, template partials, and accessibility constraints map into the reusable rendering issue without creating a second source of truth.
- [ ] T024 Map the three proving surfaces and optional FAB derivation rules into one adoption issue that depends on the descriptor and rendering issues.
- [ ] T025 Generate the issue body with `./.venv/bin/python .github/scripts/spec_kit_workflow.py issue-body specs/012-ontology-driven-operation-pages` and verify that it reflects the resolved page-pattern contract.
- [ ] T026 Generate the eventual PR body with `./.venv/bin/python .github/scripts/spec_kit_workflow.py pr-body specs/012-ontology-driven-operation-pages`.

## Notes

- Operation pages must remain action-card-first and bounded.
- Workflow-backed cards must use `workflow_key` and server-side resolution.
- FAB is optional and subordinate to the allowed card set.