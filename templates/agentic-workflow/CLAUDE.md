# CLAUDE.md

## Orchestration defaults

* Run independent tasks in parallel sessions; keep one clear objective per session.
* If work has 3+ steps, plan first before editing code.
* Delegate exploration/research/analysis to subagents to keep the main session focused.
* For framework-learning tasks, mine behavior and source separately before merging them into reusable patterns.

## 3-phase contract (required)

1. **Plan**: define scope, acceptance checks, and dependencies in `tasks/todo.md`.
2. **Execute**: implement minimal, safe changes and update task status as you go.
3. **Review**: verify outcomes from `test-results/`, summarize risks, and record lessons in `tasks/lessons.md`.

## Git delivery contract (required)

* Create or switch to a dedicated issue branch before implementation work; normal feature delivery does not happen on `main`.
* Open or refresh the matching PR as the integration container for that branch and keep it draft until the slice is ready for green validation.
* After relevant checks pass, enable auto-squash merge rather than waiting for an additional review gate.

## Right-thing contract (required)

Before implementation:

* identify the exact target surface and abstraction layer,
* note the evidence reviewed,
* record non-goals and rejected alternatives when ambiguity exists,
* choose the smallest evidence-backed change,
* define verification before editing.

If the current approach appears to target the wrong subsystem, stop, re-plan, and record the correction rather than forcing the original approach through.

## Framework-analysis mode

When analyzing a framework, demo site, or reusable UI/workflow system:

* treat the live/demo surface as behavioral evidence,
* treat repositories as implementation evidence,
* extract ontology across UI, navigation, workflow, state, permission, and cross-layer relations,
* promote only stable, atomic capabilities into skills,
* mark confidence based on whether UI behavior and source implementation agree.

## Completion gate

A task is not complete until:

* behavior is demonstrated to work,
* relevant tests/checks pass,
* the work is staged through the expected branch + PR workflow,
* and results are explicitly validated (not assumed).

## Engineering principles

* Simplicity first: smallest safe change.
* Root-cause fixes only: no temporary band-aids.
* Minimal blast radius: avoid unrelated edits.

## Self-improvement loop

After each correction, add an entry to `tasks/lessons.md` with:

* affected surface,
* error class,
* failure signature,
* root cause,
* missed evidence,
* preventive rule,
* verification added.

Use the latest files in `test-results/` as the primary evidence source for that entry instead of relying on a paraphrased memory of the failure.
