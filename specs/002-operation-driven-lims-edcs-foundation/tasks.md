---

description: "Task list for the LIMS operation foundation with shared form-engine standard"
---

# Tasks: LIMS operation foundation with shared form-engine standard

**Input**: Design documents from `/specs/002-operation-driven-lims-edcs-foundation/`
**Prerequisites**: `spec.md` and `plan.md`

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel
- **[Story]**: Maps to a user story such as `US1`
- This task file is specification-first; it defines review and issue-slicing work, not one-shot implementation.

## Phase 1: Specification ratification

- [ ] T001 Confirm that this bundle supersedes the metadata-first framing as the primary architecture direction while preserving merged metadata work as reusable primitives
- [ ] T002 Confirm that this bundle defines a LIMS-specific operation model while keeping the form-engine standard reusable across `lims` and `edcs`
- [ ] T003 Confirm the standards stance: canonical relational model plus ODM/XML and XLSX import/export artifacts, with SOP/version traceability aligned to governed clinical/laboratory execution
- [ ] T004 Confirm Viewflow remains the workflow runtime target, Sample Accession is the mandatory first specimen activity, and operational capture originates in governed activity-bound forms rather than ad hoc entry paths
- [ ] T005 Generate the initial GitHub issue body with `./.venv/bin/python .github/scripts/spec_kit_workflow.py issue-body specs/002-operation-driven-lims-edcs-foundation`

---

## Phase 2: Architecture slicing

- [ ] T010 [US1] Define `OperationDefinition` / `OperationVersion`, SOP linkage, activation lifecycle, and tenant/module scope
- [ ] T011 [US2] Define the reusable `FormPackage` / `FormPackageVersion` domain, including sections, item groups/repeats, items, identifiers/OIDs, artifacts, edit checks, and vocabulary bindings
- [ ] T012 [US2] Specify ODM/XML and XLSX import/export responsibilities, including what is first-phase versus later-phase compliance and how artifacts relate to the canonical relational model
- [ ] T013 [US3] Define workflow template, node, edge, assignee, approval, and branch-rule models compatible with Viewflow execution and its supported node palette
- [ ] T014 [US3] Specify task-level form rendering rules for full-form, section-based, group-based, and field-subset capture without duplicating version-owned items
- [ ] T015 [US4] Define runtime entities for operation runs, task runs, submissions, approvals/signatures, audit events, and material usage
- [ ] T016 [US5] Map the shared form-engine standard to EDCS visit/CRF workflows without coupling EDCS to the LIMS-specific operation/runtime model
- [ ] T017 [US2] Define reusable controlled-vocabulary governance for activity definitions, coded decisions, units, and form-package validation enforcement

---

## Phase 3: Reference operation and implementation readiness

- [ ] T020 Define the first reference operation: Sample Accession with intake, QC accept/reject, conditional storage logging, and auditable completion
- [ ] T021 Review the bundle against current `src/lims/` metadata APIs and `src/core/models.py` workflow primitives to identify migration/reuse points
- [ ] T022 Decide the first implementation issue set from this bundle: operation domain, form engine evolution, workflow builder, runtime, and reference operation
- [ ] T023 Generate the eventual PR body with `./.venv/bin/python .github/scripts/spec_kit_workflow.py pr-body specs/002-operation-driven-lims-edcs-foundation`

## Notes

- This bundle intentionally reframes the current architecture before more implementation continues.
- Existing merged metadata and vocabulary work should be treated as a foundation to reuse, not as throwaway work.
