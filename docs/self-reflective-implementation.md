# Self-reflective implementation workflow

This note defines a delivery workflow for agent-assisted implementation that improves speed while reducing rework and loops.

## Goals

* Deliver features in larger, reviewable chunks with fewer retries.
* Detect defects early using explicit reflection and verification gates.
* Keep implementation aligned with EDMP architecture and tenant-safety constraints.

## Agent roles (skills)

* **Planner**: breaks work into scoped tasks with acceptance criteria and dependencies.
* **Coder**: implements minimal, convention-aligned code changes.
* **QA**: executes targeted tests, smoke checks, and regression checks.
* **Reviewer**: performs logic/security review focused on correctness risks.
* **Integrator**: enforces merge gates and release readiness.
* **Failure triage**: clusters failures and proposes root-cause fixes.

## Execution graph

`Planner -> Coder -> QA -> Reviewer -> Integrator`

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

## Definition of done

A task is complete only when:

* acceptance checks pass,
* required tests/lint/build checks pass,
* reviewer signs off on correctness/security concerns,
* and integration gates pass without open blockers.

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
cd backend
python -m venv ../.venv
source ../.venv/bin/activate
pip install -r requirements-dev.txt
export POSTGRES_DB=edmp_test POSTGRES_USER=edmp POSTGRES_PASSWORD=edmp POSTGRES_HOST=localhost POSTGRES_PORT=5432
pytest -q
docker compose down
```
