---

description: "Task list for the Sample Accession reference operation"
---

# Tasks: Sample Accession reference operation

**Input**: Design documents from `/specs/006-sample-accession-reference-operation/`
**Prerequisites**: `spec.md` and `plan.md`

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel
- **[Story]**: Maps to a user story such as `US1`
- This task file is specification-first; it defines design and issue-slicing work, not full implementation.

## Phase 1: Reference-operation ratification

- [ ] T001 Confirm Sample Accession is the first governed reference operation on the LIMS-specific operation foundation.
- [ ] T002 Confirm the canonical workflow shape: intake -> QC -> (storage | disposition closure).
- [ ] T003 Confirm task capture binds to compiler-owned package outputs instead of workflow- or UI-defined fields, and that metadata, outcomes, storage-log data, and disposition-log data are not split into ad hoc side-entry paths.
- [ ] T004 Confirm single, batch, and EDC-linked intake are initiation modes of the same operation, not separate operation families.
- [ ] T005 Generate the issue body with `./.venv/bin/python .github/scripts/spec_kit_workflow.py issue-body specs/006-sample-accession-reference-operation`.

---

## Phase 2: Operation detail

- [ ] T010 [US1] Define the stable `sample-accession` operation identity, SOP linkage, and version lifecycle.
- [ ] T011 [US2] Define initiation semantics for single receipt, batch manifest, and EDC-linked intake.
- [ ] T012 [US3] Define the bounded accession workflow and QC-driven branching contract.
- [ ] T013 [US3] Define task-capture bindings for intake, QC, storage logging, and disposition closure.
- [ ] T014 [US4] Define runtime run/task/submission/audit/material-link expectations for accession execution, including specimen/SOP/form/actor traceability.
- [ ] T015 [US4] Define the current-to-target mapping from receiving events, discrepancies, manifests, and biospecimens into governed runtime records.
- [ ] T016 [US5] Define how future LIMS operations should reuse this reference pattern and how EDCS reuses only the shared form-engine standard, including accession-as-prerequisite rules for downstream specimen work.

---

## Phase 3: Migration and implementation readiness

- [ ] T020 Review current `/lims/receiving/*` screens and APIs to identify which become adapters versus which must be replaced.
- [ ] T021 Review runtime-domain, ODM-engine, and workflow-builder bundles to confirm all accession interfaces are covered.
- [ ] T022 Decide first implementation issue boundaries for operation config wiring, compiler bindings, runtime adapters, and UI migration.
- [ ] T023 Generate the eventual PR body with `./.venv/bin/python .github/scripts/spec_kit_workflow.py pr-body specs/006-sample-accession-reference-operation --issue-number 111`.

## Notes

- Sample Accession is the proof case for the shared architecture, not a special-case exception.
- Keep the current receiving UX as a migration path where practical.
- Keep the compiler, workflow builder, runtime, and UI boundaries explicit in every follow-on implementation issue.
