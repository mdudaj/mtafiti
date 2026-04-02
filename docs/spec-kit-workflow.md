# Spec Kit workflow

This repository treats `spec-kit` artifacts as the primary planning and delivery source of truth for substantial work.

The workflow is intent-driven: every feature bundle must state the outcome to achieve, the system boundaries it touches, and the independently reviewable implementation units that will deliver it.

## Install and initialize

Install the CLI from the upstream repository:

```bash
uv tool install specify-cli --from git+https://github.com/github/spec-kit.git
```

In a fresh clone, initialize agent command support for your preferred assistant if needed:

```bash
specify init --here --ai copilot
```

The repository already contains project-local `.specify/` files that tailor the default `spec-kit` workflow to Mtafiti, so the generated commands should use the committed constitution and templates.

## Source-of-truth workflow

1. Ratify or update `.specify/constitution.md`.
2. Create or refine the feature spec with `/speckit.specify`.
3. Produce the implementation plan with `/speckit.plan`.
4. Produce the task breakdown with `/speckit.tasks`.
5. Generate GitHub issue and PR bodies from the feature bundle.
6. Mirror executable work into SQL todos and then implement.

For a feature directory such as `specs/012-spec-kit-workflow/`, use:

```bash
python .github/scripts/spec_kit_workflow.py validate specs/012-spec-kit-workflow
python .github/scripts/spec_kit_workflow.py issue-body specs/012-spec-kit-workflow
python .github/scripts/spec_kit_workflow.py pr-body specs/012-spec-kit-workflow --issue-number 123
```

Those outputs are designed to fit the repository's existing GitHub issue and PR contracts.

## Required artifact contract

### Spec requirements

Every `spec.md` must contain these sections:

- `Intent`
- `System Context`
- `Repository Context`
- `Goals`
- `Non-Goals`
- `Success Criteria` or `Measurable Outcomes`
- `Delivery Mapping`

The `Intent` section should stay short and outcome-focused. It answers what the feature must achieve and why it matters now.

The `System Context` section should define:

- in scope
- out of scope
- interfaces
- constraints
- dependencies

That keeps each feature human-reviewable and prevents requirements, context, and boundaries from being scattered across multiple sections.

### Plan requirements

Every `plan.md` must contain these sections:

- `Summary`
- `Technical Context`
- `Constitution Check`
- `Research & Repository Evidence`
- `Resolved Design Decisions`
- `Implementation Readiness Anchors`
- `Initial Issue Split`
- `Planned Validation`

The plan must describe the first issue split explicitly. Large features are not considered implementation-ready until the decomposition is clear enough to create independently reviewable issues.

### Task requirements

Every `tasks.md` must contain:

- `Phase 1`
- `Phase 2`
- `Phase 3`
- `Notes`

Phase 3 must map the feature to concrete implementation issues or proving surfaces rather than generic follow-up work.

## Enforcement

`python .github/scripts/spec_kit_workflow.py validate <feature-dir>` now validates section presence, not just file presence.

Validation is intentionally strict for new and revised bundles. If a feature bundle does not have the required headings, it is not ready for issue generation or implementation.

Legacy bundles created before this convention may fail validation until they are revised. Those gaps should be tracked explicitly rather than ignored.

## Required repository context

Each spec and plan should capture:

- affected services and code paths,
- relevant design docs and prior checkpoints,
- knowledge-graph nodes or generated skills that inform the slice,
- Context Hub lookups for external APIs when repository evidence is insufficient,
- planned validation commands and merge-gate checks.

That keeps issue creation, implementation, and review anchored to the same artifact bundle.

## Mapping to the existing delivery process

- `spec.md`, `plan.md`, and `tasks.md` define the intended work.
- `.github/scripts/spec_kit_workflow.py` turns that bundle into GitHub issue and PR bodies.
- SQL todos remain the execution tracker for the active session.
- Existing merge gates such as `.github/scripts/local_fast_feedback.sh --full-gate` remain mandatory before integration.

## Issue drift check

Before coding from a GitHub issue, compare the current issue body with the latest approved `spec.md`, `plan.md`, and `tasks.md` for the same feature bundle.

- If the issue still matches the bundle, proceed with implementation.
- If the issue and bundle differ, reconcile them first by updating the issue text, the bundle, or both.
- Do not treat stale issue text as authoritative once the bundle has moved.

This repository treats that comparison as a required implementation-readiness check.

## Commit and PR contract

The spec bundle defines the review unit, so commit and PR behavior must preserve that boundary:

- create one implementation branch and one implementation PR per execution issue,
- use Git-safe Conventional Commit branch names such as `feat/spec-kit-workflow`,
- use Conventional Commit messages on the branch,
- refresh the PR body from `.github/scripts/spec_kit_workflow.py pr-body <feature-dir>` when scope, validation, or issue linkage changes,
- keep the PR in draft until the issue slice is complete enough for one-pass review,
- merge via squash so the reviewed PR remains the durable history unit on `main`.

The branch history should be understandable, but agents should optimize primarily for a clear PR description, explicit validation notes, and a reviewable diff.

## Reviewability rules

- Keep the feature intent reviewable in one pass.
- Prefer independently deliverable slices over comprehensive umbrella issues.
- Do not treat issue generation as proof of artifact quality; validation and human review still govern readiness.
- If a bundle needs a long explanation of how work should be split, the plan is still underspecified.
- If implementation has to reopen scope discovery, update the bundle before continuing.
- If a PR grows beyond the linked issue boundary, split the work or revise the issue/spec bundle before requesting review.

See `docs/spec-artifact-audit-2026-03-31.md` for the current revision backlog created when this convention was adopted.

## Branch naming

`spec-kit` feature directories can keep a numeric identifier such as `012-spec-kit-workflow`, but Git branches in this repository must still use Git-safe Conventional Commit slugs such as `feat/spec-kit-workflow`.
