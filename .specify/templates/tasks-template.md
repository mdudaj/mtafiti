---

description: "Mtafiti task list template aligned to spec-first GitHub delivery"
---

# Tasks: [FEATURE NAME]

**Input**: Design documents from `/specs/[###-feature-name]/`
**Prerequisites**: `spec.md`, `plan.md`, `tasks.md`, plus supporting research artifacts when present

## Format: `[ID] [P?] [Story] [Issue?] Description`

- **[P]**: Can run in parallel (different files, no blocking dependency)
- **[Story]**: Maps to a user story such as `US1`
- **[Issue?]**: Optional GitHub issue marker such as `GH-123`
- Include exact file paths in descriptions
- Keep each task small enough to map cleanly into issue, branch, and PR progress

## Phase 1: Spec and Workflow Alignment

- [ ] T001 Confirm `spec.md` reflects the latest clarified scope
- [ ] T002 Confirm `plan.md` passes the constitution check
- [ ] T003 Generate or refresh issue body with `python .github/scripts/spec_kit_workflow.py issue-body specs/[###-feature-name]`
- [ ] T004 Mirror executable work into SQL todos and dependency tracking

---

## Phase 2: Foundational Work

- [ ] T005 Establish shared prerequisites, migrations, contracts, or infra needed before user-story work starts
- [ ] T006 [P] Add or update tests that guard the foundational behavior
- [ ] T007 [P] Update documentation, knowledge graph, or skills inputs required by the foundation

**Checkpoint**: Foundational work is complete and user-story slices can proceed independently

---

## Phase 3: User Story 1 - [Title] (Priority: P1)

**Goal**: [What this story delivers]

**Independent Test**: [How to validate the story in isolation]

- [ ] T010 [P] [US1] Add or update tests in [exact path]
- [ ] T011 [P] [US1] Implement model/service changes in [exact path]
- [ ] T012 [US1] Wire endpoints, UI, or task behavior in [exact path]
- [ ] T013 [US1] Validate and document the slice

---

## Phase 4: User Story 2 - [Title] (Priority: P2)

**Goal**: [What this story delivers]

**Independent Test**: [How to validate the story in isolation]

- [ ] T020 [P] [US2] Add or update tests in [exact path]
- [ ] T021 [P] [US2] Implement model/service changes in [exact path]
- [ ] T022 [US2] Wire endpoints, UI, or task behavior in [exact path]
- [ ] T023 [US2] Validate and document the slice

---

## Phase N: Integration and PR Readiness

- [ ] T900 Re-run targeted validation and required merge-gate checks
- [ ] T901 Generate or refresh PR body with `python .github/scripts/spec_kit_workflow.py pr-body specs/[###-feature-name]`
- [ ] T902 Update issue checklist, risk notes, and done/blocker state
- [ ] T903 Commit, push, open PR, and squash merge after review

## Notes

- `spec.md` and `plan.md` remain the canonical source for issue and PR generation.
- If scope changes materially, update the spec bundle first and regenerate downstream artifacts.
