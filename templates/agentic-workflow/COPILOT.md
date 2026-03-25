# COPILOT.md

## Orchestration defaults (GitHub Copilot CLI)

* Run independent work in parallel lanes/sessions; keep one objective per lane.
* If work has 3+ steps, start in plan mode before implementation.
* Use subagents/tools for exploration and batch verification to keep context clean.

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
