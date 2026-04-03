# Reference Bundle And Publication Invariants

## Objective

Harden the authored `sample-accession` reference bundle so operation,
workflow, and form-package publication behavior remains explicit, immutable,
and reviewable. This slice should make version identity, SOP linkage, and
runtime defaults first-class publication invariants instead of incidental
behavior spread across provisioning helpers.

## Spec Kit artifacts

- Spec path: `specs/006-sample-accession-reference-operation/spec.md`
- Plan path: `specs/006-sample-accession-reference-operation/plan.md`
- Tasks path: `specs/006-sample-accession-reference-operation/tasks.md`
- Generated from: validated split proposal recorded in the `Initial Issue Split`
  section of `specs/006-sample-accession-reference-operation/plan.md`

## Deliverables

- [ ] Make the authored `sample-accession` publication contract explicit for
      operation, workflow, and package versions.
- [ ] Harden idempotent reference-bundle provisioning around immutable
      published-version expectations.
- [ ] Add or tighten tests proving publication invariants, runtime defaults,
      and any required SOP/version metadata behavior.

## Acceptance Criteria

- [ ] Published `sample-accession` operation, workflow, and package versions are
      treated as immutable authored records.
- [ ] Reference-bundle provisioning remains idempotent and does not silently
      mutate active published records.
- [ ] SOP linkage and runtime-default expectations are explicit where the
      reference bundle is authored or materialized.
- [ ] Targeted tests pass.
- [ ] Relevant docs or bundle notes are updated if publication behavior changes.
- [ ] Merge gate checks pass.

## Dependencies

- Depends on: `#111`
- Blocks: Receiving-adapter hardening and UI migration work that rely on stable
  reference-bundle invariants.

## References

- Roadmap item: Sample Accession reference operation follow-on split from `#111`
- Design docs:
  - `specs/006-sample-accession-reference-operation/spec.md`
  - `specs/006-sample-accession-reference-operation/plan.md`
- Spec bundle: `specs/006-sample-accession-reference-operation/`
- Primary current surfaces:
  - `src/lims/services.py`
  - `src/tests/test_lims_sample_accession_reference_api.py`

## Handoff contract (required updates during execution)

- Scope boundary: authored Sample Accession bundle publication invariants only
- Changed files:
- Risk notes:
- Done/blocker state: