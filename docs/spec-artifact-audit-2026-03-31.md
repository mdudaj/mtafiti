# Spec Artifact Audit - 2026-03-31

This audit records which specification artifacts comply with the repository's new intent-driven `spec-kit` convention and which artifacts need revision.

The convention is documented in `docs/spec-kit-workflow.md` and enforced by `.github/scripts/spec_kit_workflow.py validate`.

## Review basis

The audit uses these rules:

- every `spec.md` must include `Intent`, `System Context`, `Repository Context`, `Goals`, `Non-Goals`, `Success Criteria`, and `Delivery Mapping`
- every `plan.md` must include `Summary`, `Technical Context`, `Constitution Check`, `Research & Repository Evidence`, `Resolved Design Decisions`, `Implementation Readiness Anchors`, `Initial Issue Split`, and `Planned Validation`
- every `tasks.md` must include `Phase 1`, `Phase 2`, `Phase 3`, and `Notes`
- issue chains should mirror the bundle decomposition and avoid duplicate parents or superseded design umbrellas

## Ready bundles

### `011-ontology-driven-admin-shell`

Status: ready after revision.

Why it is ready:

- now includes explicit `Intent` and `System Context`
- plan now includes `Initial Issue Split`
- issue chain `#130` through `#133` matches the bundle decomposition

### `012-ontology-driven-operation-pages`

Status: ready after revision.

Why it is ready:

- includes explicit `Intent`, `System Context`, and bounded page-pattern rules
- plan includes explicit parent-plus-three-child issue split
- issue chain `#134` through `#137` matches the bundle decomposition

## Bundles requiring revision

### `001-metadata-vocabularies-and-form-schemas`

Needs revision because:

- `spec.md` lacks explicit `Intent`, `System Context`, `Goals`, and `Non-Goals`
- `plan.md` lacks `Research & Repository Evidence`, `Resolved Design Decisions`, `Implementation Readiness Anchors`, and `Initial Issue Split`

Required improvement:

- restate the feature as one outcome-focused intent
- define in-scope and out-of-scope boundaries explicitly
- convert the plan from general design prose into implementation-ready decomposition

### `002-operation-driven-lims-edcs-foundation`

Needs revision because:

- `spec.md` lacks explicit `Intent`, `System Context`, `Goals`, and `Non-Goals`
- `plan.md` lacks `Research & Repository Evidence`, `Resolved Design Decisions`, `Implementation Readiness Anchors`, and `Initial Issue Split`

Required improvement:

- make the architectural intent more concise and reviewable
- define what is still active architecture guidance versus migration prior art
- split the implementation path into child issues before more work is generated from it

### `003-operation-runtime-domain`

Needs revision because:

- `spec.md` lacks explicit `Intent` and `System Context`
- `plan.md` lacks `Resolved Design Decisions`, `Implementation Readiness Anchors`, and `Initial Issue Split`

Required improvement:

- normalize runtime-domain intent and context into the new contract
- document what remains unresolved versus already decided
- define issue split if any follow-on implementation work is still expected

### `004-odm-form-engine-foundation`

Needs revision because:

- `spec.md` lacks explicit `Intent` and `System Context`
- `plan.md` lacks `Resolved Design Decisions`, `Implementation Readiness Anchors`, and `Initial Issue Split`

Required improvement:

- express the compiler/validator outcome as a compact intent
- add system boundaries and integration interfaces explicitly
- convert the plan into implementation-ready units if the issue remains active

### `005-workflow-builder-foundation`

Needs revision because:

- `spec.md` lacks explicit `Intent` and `System Context`
- `plan.md` lacks `Resolved Design Decisions`, `Implementation Readiness Anchors`, and `Initial Issue Split`

Required improvement:

- normalize builder intent and system context
- document the child issue decomposition if further implementation remains open

### `006-sample-accession-reference-operation`

Needs revision because:

- `spec.md` lacks explicit `Intent` and `System Context`
- `plan.md` lacks `Resolved Design Decisions`, `Implementation Readiness Anchors`, and `Initial Issue Split`

Required improvement:

- clarify whether this is still a live reference-operation bundle or should be decomposed into implementation slices
- add explicit readiness anchors and child issue split before more issue generation

### `007-behavioral-ontology-skill-graph`

Needs revision because:

- `spec.md` lacks explicit `Intent`, `System Context`, `Goals`, and `Non-Goals`
- `plan.md` lacks `Research & Repository Evidence`, `Resolved Design Decisions`, `Implementation Readiness Anchors`, and `Initial Issue Split`

Required improvement:

- make the behavioral-capture intent small and outcome-focused
- separate research workflow from implementation workflow
- define whether this bundle is still active or archival prior art

### `008-viewflow-demo-behavioral-capture`

Needs revision because:

- `spec.md` lacks explicit `Intent`, `System Context`, `Goals`, and `Non-Goals`
- `plan.md` lacks `Research & Repository Evidence`, `Resolved Design Decisions`, `Implementation Readiness Anchors`, and `Initial Issue Split`

Required improvement:

- state one bounded capture outcome
- document interfaces and limits clearly
- define issue split only if more implementation work is still active

### `009-behavioral-pattern-promotion-and-diff`

Needs revision because:

- `spec.md` lacks explicit `Intent`, `System Context`, `Goals`, and `Non-Goals`
- `plan.md` lacks `Research & Repository Evidence`, `Resolved Design Decisions`, `Implementation Readiness Anchors`, and `Initial Issue Split`

Required improvement:

- restate the promotion-and-diff work as a compact intent
- normalize plan structure to match current repository conventions

### `010-behavioral-artifact-ingestion-and-playwright`

Needs revision because:

- `spec.md` lacks explicit `Intent`, `System Context`, `Goals`, and `Non-Goals`
- `plan.md` lacks `Constitution Check`, `Research & Repository Evidence`, `Resolved Design Decisions`, `Implementation Readiness Anchors`, and `Initial Issue Split`
- `tasks.md` lacks a `Notes` section

Required improvement:

- normalize the bundle to the current artifact contract before generating more work from it
- clarify what remains active implementation versus completed harness setup

## Issues requiring revision or cleanup

### Duplicate issue chain

- `#126`, `#127`, `#128`, `#129`

Why revision is needed:

- these duplicate the newer admin-shell chain `#130` through `#133`
- they create ambiguity about which parent and child issues are authoritative

Required change:

- close them as duplicates of `#130` through `#133`

### Completed-but-open design issues

- `#101`, `#108`, `#110`

Why revision is needed:

- the issue comments indicate the design goal is already satisfied or superseded
- leaving them open makes the backlog look less actionable than it is

Required change:

- close them with explicit status reason, or reopen only after rewriting them as active implementation-parent issues

### Broad design umbrellas still needing decomposition or closure

- `#107`, `#109`, `#111`

Why revision is needed:

- they are still framed as broad design trackers rather than implementation-ready issue chains
- they do not yet use the parent-plus-child structure now required for substantial work

Required change:

- either decompose them into explicit child issues that match revised bundles, or close them as satisfied by later merged work and open narrower successors

## Out-of-scope issues for this audit

- `#87` through `#90`

These are not evaluated here because they are not current `spec-kit` parent or child issues.

## Recommended next revision order

1. close duplicate issue chain `#126` through `#129`
2. close or restate `#101`, `#108`, and `#110`
3. revise legacy bundles `001` through `010` before generating new work from them
4. continue implementation only from the ready chains `#130` through `#137`