---

description: "Task list for the ODM form engine foundation"
---

# Tasks: ODM form engine foundation

**Input**: Design documents from `/specs/004-odm-form-engine-foundation/`
**Prerequisites**: `spec.md` and `plan.md`

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel
- **[Story]**: Maps to a user story such as `US1`
- This task file is specification-first; it defines design and issue-slicing work, not full implementation.

## Phase 1: Engine-boundary ratification

- [ ] T001 Confirm the ODM engine is a standalone compiler/validator subsystem.
- [ ] T002 Confirm Django/Viewflow/django-material are downstream orchestration/UI consumers, not the form compiler.
- [ ] T003 Confirm the OpenClinica-style governed package model as the design anchor.
- [ ] T004 Confirm source artifacts and compiled outputs are separate concerns.
- [ ] T005 Generate the issue body with `./.venv/bin/python .github/scripts/spec_kit_workflow.py issue-body specs/004-odm-form-engine-foundation`.

---

## Phase 2: Engine detail

- [ ] T010 [US1] Define source artifact ingestion for XLSX and ODM/XML.
- [ ] T011 [US1] Define canonical package/version/section/group/item/choice structures.
- [ ] T012 [US2] Define semantic validation responsibilities owned by the compiler.
- [ ] T013 [US1] Define compilation outputs for runtime binding and UI rendering.
- [ ] T014 [US3] Define publication freeze and immutable compiled version behavior.
- [ ] T015 [US4] Define orchestration/UI consumption contracts that forbid compiler logic leakage into downstream layers.
- [ ] T016 [US2] Define diagnostics/error surfaces for governed authoring workflows.

---

## Phase 3: Migration and implementation readiness

- [ ] T020 Review current metadata schema/version/field models to identify reuse, rename, and replacement boundaries.
- [ ] T021 Review vocabulary/domain APIs as reusable compiler-owned choice-list foundations.
- [ ] T022 Decide first implementation issue boundaries for parser adapters, canonical model, compiler services, and export contracts.
- [ ] T023 Generate the eventual PR body with `./.venv/bin/python .github/scripts/spec_kit_workflow.py pr-body specs/004-odm-form-engine-foundation --issue-number 109`.

## Notes

- The compiler is the authority for form meaning.
- Workflow and UI layers consume compiler outputs and must not become shadow compilers.
- Current metadata models are migration sources, not the final OpenClinica-style engine.
