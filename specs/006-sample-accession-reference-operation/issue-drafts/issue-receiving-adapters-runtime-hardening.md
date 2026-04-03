# Receiving Adapters To Governed Runtime Hardening

## Objective

Tighten the single, batch, and EDC transitional receiving adapters so Sample
Accession execution semantics consistently flow through the governed runtime.
This slice should focus on `OperationRun`, `TaskRun`, `SubmissionRecord`,
approvals, discrepancies, and storage or disposition outcomes rather than on
redefining the reference bundle or redesigning the UI.

## Spec Kit artifacts

- Spec path: `specs/006-sample-accession-reference-operation/spec.md`
- Plan path: `specs/006-sample-accession-reference-operation/plan.md`
- Tasks path: `specs/006-sample-accession-reference-operation/tasks.md`
- Generated from: validated split proposal recorded in the `Initial Issue Split`
  section of `specs/006-sample-accession-reference-operation/plan.md`

## Deliverables

- [ ] Review and harden the single, batch, and EDC receiving adapters so all
      initiation modes produce consistent governed runtime evidence.
- [ ] Tighten accepted and rejected branch behavior across QC, storage logging,
      discrepancy creation, and terminal outcomes.
- [ ] Add or refine runtime-facing tests to prove adapter parity and auditable
      accession evidence across initiation modes.

## Acceptance Criteria

- [ ] Single, batch, and EDC-linked initiation modes all create the same
      governed `sample-accession` operation family with mode-specific origin
      metadata only.
- [ ] Accepted and rejected branches are explicit and consistent in runtime
      records, discrepancies, and storage/disposition outcomes.
- [ ] Task-linked submissions and runtime transitions remain auditable and
      traceable through the governed runtime surfaces.
- [ ] Targeted tests pass.
- [ ] Relevant docs or bundle notes are updated if adapter/runtime behavior
      changes materially.
- [ ] Merge gate checks pass.

## Dependencies

- Depends on: `#111`, and the reference-bundle publication invariants slice
  once opened if authored bundle rules need to settle first.
- Blocks: UI migration work that needs a stable runtime adapter contract.

## References

- Roadmap item: Sample Accession reference operation follow-on split from `#111`
- Design docs:
  - `specs/006-sample-accession-reference-operation/spec.md`
  - `specs/006-sample-accession-reference-operation/plan.md`
- Spec bundle: `specs/006-sample-accession-reference-operation/`
- Primary current surfaces:
  - `src/lims/services.py`
  - `src/tests/test_lims_accessioning_api.py`
  - `src/tests/test_lims_sample_accession_reference_api.py`

## Handoff contract (required updates during execution)

- Scope boundary: transitional receiving adapters and governed runtime behavior
- Changed files:
- Risk notes:
- Done/blocker state: