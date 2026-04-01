# Portable agentic workflow template

This template packages a parallel-agent workflow that can be copied into any repository and used with both Claude Code and GitHub Copilot CLI.

## What it includes

* `CLAUDE.md`: orchestration and quality rules for Claude Code sessions.
* `COPILOT.md`: equivalent rules for GitHub Copilot CLI sessions.
* `.github/copilot-instructions.md`: repository-level Copilot coding guardrails.
* `.agentic/right-thing.yaml`: machine-readable decision contract for choosing the right target surface.
* `tasks/todo.md`: 3-phase execution tracker (Plan, Execute, Review).
* `tasks/lessons.md`: persistent lessons learned and anti-repeat rules.

## Bootstrap into a repo

From this repository root:

```bash
.github/scripts/scaffold_agentic_workflow.sh /path/to/target/repo
```

By default, existing files are preserved. Use `--force` to overwrite template-managed files.
Use `--dry-run` to preview files that would be written without changing the target repo.

## Core operating model

1. Run multiple independent sessions in parallel.
2. Require planning for work with 3+ steps.
3. Confirm the correct target surface before editing code.
4. Execute in three phases: plan, execute, review.
5. Deliver implementation work on an issue branch with a matching draft PR instead of direct-to-`main` commits.
6. Verify before completion (targeted checks, then merge-gate checks).
7. Squash merge only after the PR is ready and validation is green.
8. Persist validation artifacts in `test-results/` and record corrections in `tasks/lessons.md` so future sessions avoid repeats.

## Behavioral ontology upgrade profile

This template can also support framework-learning tasks where the objective is to mine reusable UI/workflow/navigation patterns from a live demo surface and the corresponding source code.

Use this profile when you need to analyze systems such as Viewflow, django-material, or a framework demo application.

### What to add on top of the base workflow

* Crawl the behavioral surface first: pages, menus, actions, state transitions, and permission-driven variations.
* Read source repositories as implementation truth: runtime classes, templates, components, and configuration patterns.
* Build a connected ontology across UI, navigation, workflow, state, and permissions.
* Extract atomic skills with dependencies and confidence, rather than one large framework summary.
* Evolve the current harness outputs instead of creating a separate parallel harness.

### Suggested output families

* `ontology/`
* `skills/`
* `patterns/`
* `components/`

### Confidence rule

* `high confidence`: UI/demo behavior and source implementation both support the pattern
* `low confidence`: only one source supports it so far

## Right-thing contract

Before implementation, the agent should prove:

1. the requested outcome is understood,
2. the target subsystem or abstraction layer is identified,
3. competing candidate surfaces were rejected for explicit reasons when ambiguity exists,
4. relevant evidence was reviewed before editing,
5. non-goals are listed so the fix stays scoped,
6. verification commands are selected before code changes begin.

The portable machine-readable contract for this lives in `.agentic/right-thing.yaml`.
