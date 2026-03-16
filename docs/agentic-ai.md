# Agentic AI execution design notes

This note defines controls for tenant-safe agentic AI workflows in Mtafiti.

## Goals

* Ensure agent execution remains tenant-isolated and auditable.
* Restrict agents to approved tools and bounded runtime.
* Integrate agent execution with RabbitMQ eventing conventions.

## Guardrail requirements

* Agent runs must carry explicit tenant context.
* Tools are allowlisted; no arbitrary tool invocation.
* Direct database access from agents is prohibited.
* Execution timeout and cancellation must be enforced per run.
* Prompts and outputs are logged with retention controls.

## Execution lifecycle

1. User/system requests agent run.
2. Policy and role checks authorize run + tool set.
3. Run is enqueued and executed in tenant context.
4. Start/completion/failure events are emitted.
5. Audit record stores inputs, outputs, tool invocations, and outcome metadata.

## Implemented scaffold slice

* API surface:
  * `POST/GET /api/v1/agent/runs`
  * `POST /api/v1/agent/runs/{run_id}/transition`
* Tenant-scoped run lifecycle statuses: `queued`, `running`, `completed`, `failed`, `cancelled`, `timed_out`.
* Enforced tool allowlist (`catalog.search`, `asset.read`, `contract.read`, `quality.read`, `lineage.read`, `governance.read`).
* Bounded runtime controls:
  * Required timeout range enforcement (`5..3600` seconds)
  * Explicit timeout materialization transition (`action=materialize_timeouts`)
  * Explicit cancellation transition (`action=cancel`)
* Event and audit conventions for create/transition mutations using `agent.run.*` event names.

## Implementation quality requirement

All Python code for this slice adheres to the repository PEP 8 requirement documented in `README.md` and `docs/self-reflective-implementation.md`.

## Required event fields

* `tenant_id`
* `correlation_id`
* `run_id`
* `actor_id` (when user-initiated)
* `timestamp`

## Non-goals (this increment)

* Unrestricted autonomous execution across all platform resources.
* Long-lived agents bypassing governance and approval paths.
