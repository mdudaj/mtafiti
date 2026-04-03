# Reference And Receiving UI Migration Cleanup

## Objective

Align the Sample Accession reference and receiving surfaces with the governed
runtime model so the UI communicates runtime ownership and adapter status
clearly. This slice should clean up how `/lims/reference/operations/sample-accession/`
and `/lims/receiving/*` present the transition from receiving-oriented entry
flows to governed Sample Accession execution.

## Spec Kit artifacts

- Spec path: `specs/006-sample-accession-reference-operation/spec.md`
- Plan path: `specs/006-sample-accession-reference-operation/plan.md`
- Tasks path: `specs/006-sample-accession-reference-operation/tasks.md`
- Generated from: validated split proposal recorded in the `Initial Issue Split`
  section of `specs/006-sample-accession-reference-operation/plan.md`

## Deliverables

- [ ] Review the reference-operation and receiving UI surfaces for misleading or
      mixed transitional/final boundary language.
- [ ] Update the relevant views and templates so governed runtime ownership and
      adapter semantics are explicit.
- [ ] Add or refine focused UI tests covering the resulting reference-operation
      and receiving presentation behavior.

## Acceptance Criteria

- [ ] The reference Sample Accession page clearly communicates the reference
      bundle role and current governed runtime relationship.
- [ ] Receiving launchpads and entry pages communicate that they are governed
      runtime entry adapters rather than isolated standalone flows.
- [ ] UI behavior remains consistent with the validated Sample Accession spec
      bundle and does not reintroduce page-local ownership ambiguity.
- [ ] Targeted tests pass.
- [ ] Relevant docs or bundle notes are updated if UI migration semantics
      change materially.
- [ ] Merge gate checks pass.

## Dependencies

- Depends on: `#111`, and on the runtime-hardening slice if UI wording or flow
  depends on finalized adapter semantics.
- Blocks: none required; this is primarily a cleanup and migration-clarity slice.

## References

- Roadmap item: Sample Accession reference operation follow-on split from `#111`
- Design docs:
  - `specs/006-sample-accession-reference-operation/spec.md`
  - `specs/006-sample-accession-reference-operation/plan.md`
- Spec bundle: `specs/006-sample-accession-reference-operation/`
- Primary current surfaces:
  - `src/lims/views.py`
  - `src/lims/templates/lims/reference_sample_accession.html`
  - `src/lims/templates/lims/receiving.html`
  - `src/tests/test_lims_ui.py`

## Handoff contract (required updates during execution)

- Scope boundary: Sample Accession reference and receiving UI migration clarity
- Changed files:
- Risk notes:
- Done/blocker state: