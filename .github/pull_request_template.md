# Pull Request

## Summary

Describe what this PR changes, why it is needed now, and what is intentionally left out of scope.

## Review unit

- [ ] PR scope maps to exactly one execution issue / implementation slice.
- [ ] PR is still small enough for one-pass review.
- [ ] PR is draft if any acceptance criteria or validation notes are still incomplete.
- [ ] Work was delivered on this branch/PR instead of by direct-to-`main` implementation.

## Spec Kit artifacts

- [ ] Spec path recorded.
- [ ] Plan path recorded.
- [ ] Tasks path recorded.
- [ ] PR body refreshed from `python .github/scripts/spec_kit_workflow.py pr-body specs/<feature-dir>`.

## Issue contract

- [ ] Linked execution issue includes Objective, Deliverables, Acceptance Criteria, Dependencies, and References.
- [ ] Scope boundary for this PR is explicit and matches the issue deliverables.

## Commit contract

- [ ] Branch name uses the repository's Git-safe Conventional Commit slug format.
- [ ] Branch commits use Conventional Commit subjects.
- [ ] Final integration path for this work is squash merge after review and green checks.
- [ ] No unrelated refactors, drive-by fixes, or broad rename-only churn are mixed into this PR.

## Handoff contract

- [ ] Changed files and risk notes are captured in PR description.
- [ ] Done/blocker state is explicit (no implicit “follow-up later” gaps).
- [ ] Reviewers can see the primary files or behaviors to inspect first.

## Documentation chunk

- [ ] This docs PR is a meaningful batch (target: 3+ docs files when docs-only).
- [ ] Chunk selected: Platform core / Execution modules / Security & ops / Governance domains.
- [ ] Roadmap and README links are updated together when new design docs are introduced.
- [ ] Acceptance criteria and non-goals are present in each newly added design doc.
- [ ] Cross-doc references are updated so the chunk is reviewable end-to-end in one pass.

## Validation

- [ ] Ran tests/checks relevant to this change.
- [ ] Listed the concrete commands or manual checks used for validation in the PR body.
