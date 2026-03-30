---

description: "Task list for behavioral pattern promotion, browser capture, and run diffing"
---

# Tasks: Behavioral pattern promotion, browser capture, and run diffing

**Input**: Design documents from `/specs/009-behavioral-pattern-promotion-and-diff/`
**Prerequisites**: `spec.md` and `plan.md`

## Phase 1: Scope Alignment

- [ ] T001 Confirm `spec.md` captures run history, promotion, browser mode, and diff scope
- [ ] T002 Confirm `plan.md` reflects the intended implementation and validation steps
- [ ] T003 Generate or refresh issue body with `python .github/scripts/spec_kit_workflow.py issue-body specs/009-behavioral-pattern-promotion-and-diff`

---

## Phase 2: Capture Workflow Enhancements

- [ ] T010 Add run-specific storage under the behavioral capture root
- [ ] T011 Promote captured page models into pattern and ontology-candidate artifacts
- [ ] T012 Add optional browser-backed fetching with configurable external commands

---

## Phase 3: Diffing and Documentation

- [ ] T020 Add run-diff output for added, removed, and structurally changed routes
- [ ] T021 Update bootstrap metadata and README documentation for browser mode and diffs
- [ ] T022 Keep latest-artifact outputs aligned with stored run history

---

## Phase 4: Validation

- [ ] T030 Add focused tests for promotion, browser fetching, and run diffs
- [ ] T031 Extend bootstrap tests for new manifest and guide metadata
- [ ] T032 Run targeted validation and record results

## Notes

- This slice still stops short of automatically merging promoted patterns back into the committed ontology or skill graph.
- Browser-backed capture is optional by design and depends on an available external dump command.