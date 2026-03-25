# CLAUDE.md

## Orchestration defaults

* Run independent tasks in parallel sessions; keep one clear objective per session.
* If work has 3+ steps, plan first before editing code.
* Delegate exploration/research/analysis to subagents to keep the main session focused.

## 3-phase contract (required)

1. **Plan**: define scope, acceptance checks, and dependencies in `tasks/todo.md`.
2. **Execute**: implement minimal, safe changes and update task status as you go.
3. **Review**: verify outcomes, summarize risks, and record lessons in `tasks/lessons.md`.

## Right-thing contract (required)

Before implementation:

* identify the exact target surface and abstraction layer,
* note the evidence reviewed,
* record non-goals and rejected alternatives when ambiguity exists,
* choose the smallest evidence-backed change,
* define verification before editing.

If the current approach appears to target the wrong subsystem, stop, re-plan, and record the correction rather than forcing the original approach through.

## Completion gate

A task is not complete until:

* behavior is demonstrated to work,
* relevant tests/checks pass,
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
