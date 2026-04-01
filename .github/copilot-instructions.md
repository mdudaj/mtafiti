# Copilot repository instructions

## Workflow contract

* Plan first for tasks with 3+ steps.
* Use a 3-phase flow: Plan -> Execute -> Review.
* Confirm the right target surface before making changes.
* Track work items in `tasks/todo.md`; track lessons in `tasks/lessons.md`.
* Start implementation work from a dedicated issue branch; do not make normal delivery changes on `main`.
* Open or refresh the matching pull request for that branch and keep it in draft until scope, acceptance criteria, and validation notes are current.
* Merge implementation work by squash merge after required checks pass; do not treat direct-to-`main` commits as a normal completion path.

## Verification contract

* Run targeted checks during implementation.
* Run full repository merge-gate checks before handoff.
* Treat tasks as incomplete until verification evidence is captured.

## Framework mining contract

When the task is to learn from a framework or demo application:

* capture both behavioral evidence and source-code evidence,
* model UI, navigation, workflow, state, and permission layers explicitly,
* preserve provenance and confidence when promoting patterns into skills or components,
* prefer atomic skills with declared dependencies over broad blended recipes.

## Code-change contract

* Prefer minimal, behavior-safe changes.
* Reuse existing patterns/helpers before adding new ones.
* Avoid unrelated refactors while delivering a scoped fix.
* Reject unsupported assumptions and gather evidence when multiple surfaces could satisfy the request.

## Parallel execution contract

* Run independent slices in parallel sessions.
* Keep dependent slices sequential and explicit with dependencies.