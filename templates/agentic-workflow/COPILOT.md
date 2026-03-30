# COPILOT.md

## Orchestration defaults (GitHub Copilot CLI)

* Run independent work in parallel lanes/sessions; keep one objective per lane.
* If work has 3+ steps, start in plan mode before implementation.
* Use subagents/tools for exploration and batch verification to keep context clean.
* For framework-analysis tasks, separate behavioral evidence from source-code evidence before generalizing patterns.

## 3-phase contract (required)

1. **Plan** in `tasks/todo.md` with scope boundaries and acceptance checks.
2. **Execute** with minimal, convention-aligned code changes.
3. **Review** with test evidence and lessons recorded in `tasks/lessons.md`.

## Right-thing contract (required)

Before editing:

* identify the target surface (`docs`, `template`, `script`, `runtime`, `test`, etc.),
* list the evidence reviewed for that choice,
* list what is explicitly out of scope,
* choose the smallest supported change that satisfies the request,
* define verification before implementation.

If more than one subsystem looks plausible, compare candidate surfaces first and state why the chosen one best matches the request. Do not anchor on the first matching keyword.

## Framework-analysis mode

When the task is harness enrichment or framework mining:

* model UI, navigation, workflow, state, permission, and cross-layer links explicitly,
* capture page models and interaction flows from the visible application surface,
* validate extracted patterns against source repositories before promoting them into reusable skills,
* keep skills atomic and composable, with dependencies where needed,
* record confidence as high only when behavior and source implementation align.

## Completion gate

Do not mark done until:

* targeted checks pass,
* merge-gate checks pass (repo-defined),
* and behavior is verified end-to-end.

## Engineering principles

* Keep diffs surgical.
* Fix root causes, not symptoms.
* Avoid silent failures and broad exception swallowing.

## Self-improvement loop

After each fix, rollback, or wrong-turn correction, append a reusable rule to `tasks/lessons.md`. Prefer lessons that explain why the earlier target or fix was wrong and what evidence would have prevented it.
