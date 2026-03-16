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

## Resources to expose (to reduce looping)

* Repository symbol/code index and architecture map.
* Standard one-command runners for lint, tests, and build.
* Docker Compose-backed local test dependencies (at minimum Postgres; RabbitMQ when event-path integration is needed).
* Test-impact mapping (which tests cover changed files).
* Recent CI failures and artifact/log access.
* Known-flaky test catalog and retry policy.
* Shared task graph with dependency and ownership status.
* Clear repository conventions (patterns, guardrails, and no-go areas).

## Anti-loop controls

* Retry budget per task phase (for example: max 2 reattempts before escalation).
* Mandatory root-cause note before each retry.
* Prefer smallest safe fix; avoid speculative broad rewrites.
* Escalate to Planner when the same failure signature repeats.

## Fast feedback profile (new)

Use a two-speed execution pattern to reduce local cycle time while preserving full quality gates:

1. **Targeted loop (default while coding)**
   * Run only tests directly related to changed surfaces.
   * Command: `.github/scripts/local_fast_feedback.sh <pytest selectors>`
   * Example: `.github/scripts/local_fast_feedback.sh tests/test_printing_api.py -k gateway`
2. **Pre-integration loop (required before handoff)**
   * Run docs/openapi checks and broad backend validation.
   * Command: `.github/scripts/local_fast_feedback.sh --full-gate`

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
2. Backend tests (`pytest -q`)
3. Reviewer sign-off for correctness/security risks
4. Issue checklist updated with completed deliverables and acceptance criteria

PR checklist template: `.github/pull_request_template.md` enforces issue + handoff contract items.

## End-to-end execution policy (mandatory)

Every implementation task in this project should be executed end-to-end in one flow:

1. implement the slice,
2. run tests for the slice and then full backend suite,
3. fix discovered issues,
4. rerun tests until green,
5. then commit/push.

Tasks should not be reported as done while still waiting on test execution or post-implementation validation.

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
