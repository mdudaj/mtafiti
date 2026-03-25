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
5. Verify before completion (targeted checks, then merge-gate checks).
6. Record corrections in `tasks/lessons.md` so future sessions avoid repeats.

## Right-thing contract

Before implementation, the agent should prove:

1. the requested outcome is understood,
2. the target subsystem or abstraction layer is identified,
3. competing candidate surfaces were rejected for explicit reasons when ambiguity exists,
4. relevant evidence was reviewed before editing,
5. non-goals are listed so the fix stays scoped,
6. verification commands are selected before code changes begin.

The portable machine-readable contract for this lives in `.agentic/right-thing.yaml`.
