# Self-reflective implementation workflow

This note defines a delivery workflow for agent-assisted implementation that improves speed while reducing rework and loops.

## Goals

* Deliver features in larger, reviewable chunks with fewer retries.
* Detect defects early using explicit reflection and verification gates.
* Keep implementation aligned with Mtafiti architecture and tenant-safety constraints.

## Agent roles (skills)

* **Planner**: breaks work into scoped tasks with acceptance criteria and dependencies.
* **Coder**: implements minimal, convention-aligned code changes.
* **QA**: executes targeted tests, smoke checks, and regression checks.
* **Reviewer**: performs logic/security review focused on correctness risks.
* **Integrator**: enforces merge gates and release readiness.
* **Failure triage**: clusters failures and proposes root-cause fixes.

## Execution graph

`Planner -> Coder -> QA -> Reviewer -> Integrator`

### Parallel lane execution (Copilot `/fleet`)

Use parallel lanes for independent slices while preserving the same handoff chain:

`Planner -> (Coder -> QA -> Reviewer)xN -> Integrator`

Operator flow:

1. enable fleet mode (`/fleet`) and create one lane per independent issue/slice,
2. assign each lane the same role sequence (`Planner -> Coder -> QA -> Reviewer`),
3. use `/tasks` to monitor lane progress and blockers,
4. integrate only lanes that pass shared acceptance checks.

Do not run dependent slices in parallel if one lane requires outputs from another.

### Parallel orchestration profile (Claude + Copilot)

Adopt the same operator model across tools:

* Run multiple independent sessions in parallel (practical default: 4-8 local lanes; scale higher when tasks are truly independent).
* Keep each lane single-purpose and explicitly scoped.
* Treat the operator as orchestrator: assign, monitor, and integrate rather than waiting on one long session.
* Promote only lanes that pass shared acceptance checks.

Portable template artifacts for new repositories are provided under `templates/agentic-workflow/` and can be instantiated with:

```bash
.github/scripts/scaffold_agentic_workflow.sh /path/to/target/repo
```

Reflection edges:

* `QA -> Coder` for test failures.
* `Reviewer -> Coder` for logic/security regressions.
* `Integrator -> Planner` when scope or dependency assumptions fail.
* `Failure triage -> Planner/Coder/QA` to prevent repeated blind retries.

Use the validation artifacts under `./test-results/` as the default evidence source for those reflection edges. At minimum, review the current pytest XML report and the matching gate log before recording a lesson or choosing the next retry.

## Right-thing contract (new)

Before any code change, the active lane must establish:

1. **Objective**: what outcome is actually requested.
2. **Target surface**: which subsystem, abstraction layer, or artifact should change.
3. **Rejected alternatives**: what other plausible surfaces were considered and why they were rejected.
4. **Evidence reviewed**: docs, code paths, tests, or generated artifacts examined before editing.
5. **Non-goals**: what must not change.
6. **Verification plan**: commands or checks that will prove the fix is correct.

If multiple surfaces appear relevant, the lane should compare them explicitly before implementation instead of following the first keyword match. Wrong-target fixes should be treated as process defects and recorded in the lessons log.

## Per-phase contract

Each handoff must include:

* task id + scope boundary
* expected behavior and acceptance checks
* changed files + risk notes
* explicit done/blocker state

Handoffs without this contract should be rejected and returned.

### Issue contract (required before coding)

Each execution issue must include:

* Objective
* Deliverables checklist
* Acceptance criteria
* Dependencies (`depends on` / `blocks`)
* References to roadmap/design docs

Template: use `.github/ISSUE_TEMPLATE/delivery-work-item.md` for consistent issue setup.

Before implementing an issue, compare the live issue text against the latest approved `spec-kit` bundle (`spec.md`, `plan.md`, and `tasks.md`). If the issue drifted from the bundle, update the issue or refresh the bundle before writing code. Treat this as a required gate, not an optional review step.

### Delivery order (required)

Use this repository workflow for new implementation slices:

1. create or refresh the `spec-kit` bundle first (`spec.md`, `plan.md`, `tasks.md`),
2. generate or refresh the GitHub issue set from the spec bundle,
3. mirror executable work into SQL todos with dependencies,
4. implement one issue per branch,
5. commit and push coherent work on the branch using Conventional Commit messages,
6. open or refresh a PR generated from the same spec bundle,
7. keep the PR in draft until the issue slice is complete and validation notes are current,
8. request review only when the PR is ready for one-pass review,
9. squash merge after review passes.

Agents must treat branch -> PR -> squash merge as the default delivery path for implementation work. Direct-to-`main` changes are reserved for explicit, exceptional repository maintenance requested by the operator, not normal feature delivery.

Use `docs/spec-kit-workflow.md` and `.github/scripts/spec_kit_workflow.py` to keep issue and PR text aligned with the approved spec bundle.

### Branch naming (required)

Use Conventional Commit-style work labels, but convert them to Git-safe branch refs:

* Human-readable label / workstream: `feat: LIMS permissions`
* Git branch name: `feat/lims-permissions`

Use the same pattern for other branch types, for example `fix/...`, `docs/...`, `refactor/...`, `test/...`, and `chore/...`.

Do not use issue-number-only branches when a scoped feature/fix label is available. Git refs cannot contain `:` or spaces, so the branch must use the slash + slug form even when the human-readable convention uses `type: Title`.

### Commit conventions (required)

Commit messages must use Conventional Commits:

* Format: `type(scope optional): imperative summary`
* Examples: `feat(shell): add ontology navigation resolver`, `fix(operations): reject cross-tenant action cards`
* Preferred types: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`, `build`, `ci`, `perf`, `revert`

Use commits to record coherent implementation steps, not to curate a perfect public history inside the branch. Avoid commit titles such as `wip`, `misc fixes`, or `address feedback` with no scoped subject. When review feedback arrives, prefer additive follow-up commits on the branch; the repository keeps `main` clean by squash merging the reviewed PR.

### Pull request discipline (required)

Treat the PR, not the branch commit list, as the primary review unit.

* One execution issue maps to one implementation PR.
* Keep each PR small enough to review in one sitting and aligned to the linked issue deliverables.
* Do not mix unrelated refactors, drive-by fixes, or opportunistic renames into an implementation PR.
* Avoid combining broad file renames with logic changes unless the rename is required for the acceptance criteria.
* Use a draft PR for incomplete work instead of a reviewable PR with a `WIP` title.
* Agents should open or refresh the draft PR as part of delivery, not wait until after local implementation is effectively complete.
* Mark the PR ready only when the description, validation notes, and risk handoff are current.
* Resolve or answer review comments explicitly before merge.
* Prefer squash merge so reviewed PRs yield a clean `main` history without requiring branch-local commit curation.
* If the local branch accumulates unrelated stacked commits or the local git transport cannot publish, create a clean branch from `main` and publish only the scoped files through the repository PR tooling instead of waiting or rewriting shared history on `main`.

Maintainers who need to enforce the same merge contract at the repository-settings level should use the branch-protection runbook in `docs/operations-runbooks.md` and the helper at `.github/scripts/configure_branch_protection.py` instead of editing GitHub settings ad hoc.

## Resources to expose (to reduce looping)

* Repository symbol/code index and architecture map.
* Standard one-command runners for lint, tests, and build.
* Docker Compose-backed local test dependencies (at minimum Postgres; RabbitMQ when event-path integration is needed).
* Test-impact mapping (which tests cover changed files).
* Recent CI failures and artifact/log access.
* Known-flaky test catalog and retry policy.
* Shared task graph with dependency and ownership status.
* Clear repository conventions (patterns, guardrails, and no-go areas).

## Behavioral ontology harness profile (new)

Use this profile when the task is not a narrow repository fix, but a framework-learning or harness-enrichment request such as mining Viewflow, django-material, or a demo application for reusable implementation patterns.

### Upgrade principle

* Evolve the existing harness; do not replace it with a second disconnected system.
* Keep the current execution controls (`right-thing`, 3-phase flow, lessons, merge gates) and add a behavior-mining layer on top.

### Dual-source evidence contract

For framework-pattern extraction, the agent should treat two evidence classes as mandatory:

1. **Behavioral truth**
   * demo sites, interactive screens, menus, task states, and permission-driven UI changes
2. **Implementation truth**
   * source repositories, templates, runtime classes, and framework primitives

If a pattern is observed in both places, mark it **high confidence**. If it appears in only one place, keep it **low confidence** until confirmed.

### Multi-layer ontology contract

When mining a workflow/UI framework, capture at least these layers:

* `ui`: shells, list/detail/form/dashboard/task views, actions, and layouts
* `navigation`: menus, drawers, menu groups, visibility rules, route bindings
* `workflow`: flows, nodes, tasks, decisions, end states, runtime bindings
* `state`: process state, task state, action-triggered transitions
* `permission`: role-based visibility, task availability, view access
* `cross_layer`: links such as `MenuItem -> View -> WorkflowTask -> ProcessState -> Model`

Do not treat these as separate notes only. They should form one connected graph.

### Skill-graph contract

Extract skills as atomic capabilities, not large blended recipes.

Each skill should ideally record:

* purpose
* required inputs
* evidence sources
* dependency skills
* confidence level
* expected outputs or affected layer

Prefer skill composition over large monolithic skills. For example, a workflow page should compose navigation, UI, workflow-binding, and permission skills instead of hiding all of them in one pattern blob.

### Pattern extraction workflow

Follow this order for behavior-mining tasks:

1. map the visible application surface,
2. record page models and user interactions,
3. inspect source repositories for the runtime/template implementation,
4. align UI observations with source-level abstractions,
5. promote aligned patterns into ontology nodes and skills,
6. record confidence and unresolved gaps,
7. update reusable components only after ontology and skills are stable enough.

### Expected artifact families

When the harness grows into framework-mining mode, it should be able to persist outputs in families such as:

* ontology
* skills
* patterns
* components
* confidence or provenance annotations

The exact repository paths may vary, but the artifact split should remain explicit so mined behavior, generalized skills, and executable components are not collapsed into one file.

### Self-learning refinement

After each new implementation or newly observed pattern:

* compare the implementation with the current ontology,
* detect missing layers, overlapping skills, or wrong abstractions,
* split or merge skills where overlap is discovered,
* update provenance and confidence rather than silently rewriting prior assumptions.

## Anti-loop controls

* Retry budget per task phase (for example: max 2 reattempts before escalation).
* Mandatory root-cause note before each retry.
* Prefer smallest safe fix; avoid speculative broad rewrites.
* Escalate to Planner when the same failure signature repeats.

### Structured lesson taxonomy

To make lessons reusable across sessions, capture the correction using a small taxonomy:

* `wrong_target_surface`
* `wrong_abstraction_layer`
* `insufficient_evidence`
* `missing_verification`
* `overbroad_change`

Each lesson should state the affected surface, missed evidence, preventive rule, and verification added.

When available, cite the exact artifact paths reviewed from `./test-results/` so the next session can inspect the same failure evidence instead of relying on memory alone.

## Fast feedback profile (new)

Use a two-speed execution pattern to reduce local cycle time while preserving full quality gates:

1. **Targeted loop (default while coding)**
   * Run only tests directly related to changed surfaces.
   * Command: `.github/scripts/local_fast_feedback.sh <pytest selectors>`
   * Example: `.github/scripts/local_fast_feedback.sh tests/test_printing_api.py -k gateway`
   * Artifacts: `test-results/local-fast-feedback.log` and `test-results/pytest-targeted.xml`
2. **Pre-integration loop (required before handoff)**
   * Run docs/openapi/knowledge-graph checks and broad backend validation.
   * Command: `.github/scripts/local_fast_feedback.sh --full-gate`
   * Artifacts: `test-results/full-gate.log` and `test-results/pytest-full-gate.xml`
   * Stage any new or deleted source/doc files first (`git add -A` or equivalent), otherwise repository-inventory checks can produce false greens locally and fail in CI.

This keeps short iterations fast but still enforces the same merge-gate expectations before integration.

## Definition of done

A task is complete only when:

* acceptance checks pass,
* required tests/lint/build checks pass,
* reviewer signs off on correctness/security concerns,
* and integration gates pass without open blockers.

### Shared acceptance checks (merge gate)

Every lane must pass the same merge gate before integration:

1. Docs workflow gate (`.github/scripts/check_docs_workflow.py`)
2. OpenAPI drift gate (`.github/scripts/check_openapi_contract.py`)
3. Knowledge graph drift gate (`.github/scripts/generate_knowledge_graph.py --check`)
4. Backend tests (`pytest -q`)
5. Reviewer sign-off for correctness/security risks
6. Issue checklist updated with completed deliverables and acceptance criteria

PR checklist template: `.github/pull_request_template.md` enforces issue + handoff contract items.

## End-to-end execution policy (mandatory)

Every implementation task in this project should be executed end-to-end in one flow on its issue branch:

1. implement the slice,
2. run tests for the slice and then full backend suite,
3. fix discovered issues,
4. rerun tests until green,
5. then commit/push with Conventional Commit messages,
6. open/update the PR and refresh the spec-derived description,
7. keep the PR in draft until the slice is review-ready,
8. merge via squash after review.

Tasks should not be reported as done while still waiting on test execution or post-implementation validation.

If a follow-up commit is added after the initial validation, rerun the full pre-integration gate before pushing again. Even tiny structural files such as `__init__.py`, migrations package markers, new tests, or new migration files can change generated repository artifacts like `analysis/environment_inventory.yaml`. Stage new/deleted source-doc files before running the full gate so it validates the same tracked file set that CI will see.

### Python style requirement

All Python code changes in this repository must adhere to PEP 8 (imports, naming, whitespace, and readable line structure) and should be written to pass existing test/lint quality gates without follow-up style cleanups.

## Local QA bootstrap (recommended)

Use a deterministic local dependency bootstrap before running backend tests:

```bash
docker compose up -d --wait postgres
cd src
python -m venv ../.venv
source ../.venv/bin/activate
pip install -r requirements-dev.txt
export POSTGRES_DB=mtafiti_test POSTGRES_USER=mtafiti POSTGRES_PASSWORD=mtafiti POSTGRES_HOST=localhost POSTGRES_PORT=5432
pytest -q
docker compose down
```
