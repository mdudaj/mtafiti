# Copilot repository instructions (template)

## Workflow contract

* Plan first for tasks with 3+ steps.
* Use a 3-phase flow: Plan -> Execute -> Review.
* Confirm the right target surface before making changes.
* Track work items in `tasks/todo.md`; track lessons in `tasks/lessons.md`.

## Verification contract

* Run targeted checks during implementation.
* Run full repository merge-gate checks before handoff.
* Treat tasks as incomplete until verification evidence is captured.

## Code-change contract

* Prefer minimal, behavior-safe changes.
* Reuse existing patterns/helpers before adding new ones.
* Avoid unrelated refactors while delivering a scoped fix.
* Reject unsupported assumptions and gather evidence when multiple surfaces could satisfy the request.

## Parallel execution contract

* Run independent slices in parallel sessions.
* Keep dependent slices sequential and explicit with dependencies.
