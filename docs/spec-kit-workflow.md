# Spec Kit workflow

This repository now treats `spec-kit` artifacts as the primary planning and delivery source of truth for substantial work.

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

## Branch naming

`spec-kit` feature directories can keep a numeric identifier such as `012-spec-kit-workflow`, but Git branches in this repository must still use Git-safe Conventional Commit slugs such as `feat/spec-kit-workflow`.
